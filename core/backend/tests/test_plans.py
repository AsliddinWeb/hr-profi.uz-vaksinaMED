import textwrap
from datetime import date, timedelta

import pytest

from app import plans
from app.client_schema import validate_client_dir
from app.extensions import load_client_config
from app.modules import CORE_MODULES
from tests.conftest import login, make_user

USERS = "/api/v1/users"


@pytest.fixture
def plan_cfg(app):
    """Test uchun tarif/litsenziyani o'rnatadi va oxirida tiklaydi."""
    cfg = app.state.client_config
    before = (cfg.plan, dict(cfg.license), dict(cfg.modules))

    def set_(plan, license_=None, explicit=None):
        cfg.plan, cfg.license = plan, dict(license_ or {})
        cfg.modules = plans.resolve_modules(plan, explicit)
        plans.configure(plan, license_)

    yield set_
    cfg.plan, cfg.license, cfg.modules = before[0], before[1], before[2]
    plans.configure(before[0], before[1])


def test_resolve_modules_and_features():
    assert plans.resolve_modules(None, None) == CORE_MODULES  # tarifsiz: hammasi yoqilgan
    start = plans.resolve_modules("start", {"payroll": True, "tasks": False})
    assert start["attendance"] and not start["payroll"] and not start["face_id"] and not start["tasks"]  # tarifdan tashqari yoqilmaydi, tarifdagini o'chirish mumkin
    assert plans.resolve_modules("pro", None)["face_id"] and not plans.resolve_modules("pro", None)["ai"]
    assert plans.resolve_modules("premium", None)["ai"]
    assert plans.feature_available("face_id", "pro") and not plans.feature_available("face_id", "start") and plans.feature_available("anything", "start")
    assert plans.feature_available("ai", None)  # tarif yo'q: cheklov yo'q
    today = date(2026, 11, 1)
    assert plans.license_status({}, today) == "unlimited"
    assert plans.license_status({"valid_until": "2026-11-01"}, today) == "active"
    assert plans.license_status({"valid_until": date(2026, 10, 25)}, today) == "grace"
    assert plans.license_status({"valid_until": "2026-10-01"}, today) == "expired"


def test_client_yaml_plan_and_license(tmp_path):
    base = tmp_path / "koshi"
    base.mkdir()
    (base / "client.yaml").write_text(textwrap.dedent("name: koshi\nplan: pro\nlicense: {seats: 50, valid_until: 2027-01-01, holder: Test LLC}\nmodules: {payroll: false}\n"))
    assert validate_client_dir(base) == ([], [])
    cfg = load_client_config(base)
    assert cfg.plan == "pro" and cfg.license["seats"] == 50 and not cfg.modules["payroll"] and cfg.modules["face_id"] and not cfg.modules["ai"]
    (base / "client.yaml").write_text("name: koshi\nplan: gold\nlicense: {seats: 0, valid_until: kecha, extra: 1}\n")
    errors, _ = validate_client_dir(base)
    assert any("plan:" in e for e in errors) and any("seats" in e for e in errors) and any("valid_until" in e for e in errors) and any("license.extra" in e for e in errors)


async def test_module_gate_blocks_disabled_modules(client, plan_cfg):
    await make_user("boss", "tasischi")
    assert (await login(client, "boss")).status_code == 200
    plan_cfg("start")
    r = await client.get("/api/v1/payroll/runs")
    assert r.status_code == 403 and r.json()["detail"] == {"code": "module_disabled", "module": "payroll"}
    assert (await client.get("/api/v1/employees")).status_code == 200  # START tarifida bor
    plan_cfg("pro")
    assert (await client.get("/api/v1/payroll/runs")).status_code == 200  # PRO tarifida bor
    assert (await client.get("/api/v1/ai/status")).json()["detail"]["code"] == "module_disabled"  # AI faqat PREMIUM
    assert "plan" in (await client.get("/api/v1/meta")).json()


async def test_seat_limit_and_license_expiry(client, plan_cfg):
    await make_user("boss", "tasischi")
    assert (await login(client, "boss")).status_code == 200
    plan_cfg("pro", {"seats": 3, "valid_until": (date.today() + timedelta(days=30)).isoformat(), "holder": "Test"})
    p = (await client.get("/api/v1/plan")).json()
    assert p["plan"] == "pro" and p["license"]["seats"] == 3 and p["license"]["used"] == 1 and p["license"]["free"] == 2 and p["license"]["status"] == "active"
    assert next(f for f in p["features"] if f["key"] == "ai")["available"] is False
    assert next(f for f in p["features"] if f["key"] == "face_id")["available"] is True
    assert [x["price_usd"] for x in p["plans"]] == [3, 5, 7]

    ids = []
    for n in range(2):
        r = await client.post(USERS, json={"full_name": f"Ali Valiyev{n}", "role_key": "farmasevt"})
        assert r.status_code == 201, r.text
        ids.append(r.json()["user"]["id"])
    r = await client.post(USERS, json={"full_name": "Uchinchi Odam", "role_key": "farmasevt"})
    assert r.status_code == 409 and r.json()["detail"] == {"code": "seat_limit", "seats": 3}
    # bittasini o'chirsak o'rin bo'shaydi; qayta yoqish ham chegaraga bo'ysunadi
    assert (await client.post(f"{USERS}/{ids[0]}/deactivate")).status_code == 200
    assert (await client.post(USERS, json={"full_name": "Yangi Odam", "role_key": "farmasevt"})).status_code == 201
    assert (await client.post(f"{USERS}/{ids[0]}/activate")).json()["detail"]["code"] == "seat_limit"

    # muddati o'tgan litsenziya: yangi foydalanuvchi qo'shib bo'lmaydi, kirish ishlayveradi
    plan_cfg("pro", {"seats": 50, "valid_until": (date.today() - timedelta(days=60)).isoformat()})
    assert (await client.post(USERS, json={"full_name": "Eski Muddat", "role_key": "farmasevt"})).json()["detail"]["code"] == "license_expired"
    assert (await client.get("/api/v1/plan")).json()["license"]["status"] == "expired"
    plan_cfg(None)  # tarifsiz: cheklov yo'q
    assert (await client.post(USERS, json={"full_name": "Tarifsiz Odam", "role_key": "farmasevt"})).status_code == 201


async def test_custom_roles_need_pro(client, plan_cfg):
    await make_user("boss", "tasischi")
    assert (await login(client, "boss")).status_code == 200
    roles = (await client.get("/api/v1/roles")).json()
    far = next(r for r in roles if r["key"] == "farmasevt")
    plan_cfg("start")
    r = await client.put(f"/api/v1/roles/{far['id']}/permissions", json={"permissions": far["permissions"]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "plan_feature" and r.json()["detail"]["required"] == "pro"
    plan_cfg("pro")
    assert (await client.put(f"/api/v1/roles/{far['id']}/permissions", json={"permissions": far["permissions"]})).status_code == 200
