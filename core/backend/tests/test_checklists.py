from datetime import datetime, timedelta

import pytest

from app.services import checklists as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

C = "/api/v1/checklists"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=tz())
LAT, LNG = 41.3, 69.3
ITEMS = [
    {"section": "Tozalik", "text": "Pol toza", "kind": "yesno", "weight": 2},
    {"section": "Tozalik", "text": "Vitrina holati", "kind": "score", "weight": 3},
    {"section": "Hujjat", "text": "Sertifikatlar bor", "kind": "yesno", "weight": 5, "critical": True},
    {"text": "Reklama", "kind": "yesno", "weight": 1, "required": False},
]


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    fn = lambda: state["t"]  # noqa: E731
    for mod in ("app.api.checklists", "app.services.checklists"):
        monkeypatch.setattr(f"{mod}.now", fn, raising=False)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def setup(new_client):
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    co, co_id = await as_user(new_client, "coord", "koordinator")
    co2, co2_id = await as_user(new_client, "coord2", "koordinator")
    mg, mg_id = await as_user(new_client, "mudir", "mudir")
    far, _ = await as_user(new_client, "far", "farmasevt")
    b1 = (await hr.post("/api/v1/branches", json={"number": 1, "name": "Filial 1", "latitude": LAT, "longitude": LNG, "geofence_radius_m": 100, "coordinator_user_id": co_id, "manager_user_id": mg_id})).json()
    b2 = (await hr.post("/api/v1/branches", json={"number": 2, "name": "Filial 2", "coordinator_user_id": co2_id})).json()
    tpl = (await hr.post(f"{C}/templates", json={"name": "Haftalik", "items": ITEMS})).json()
    return {"hr": hr, "co": co, "co2": co2, "mg": mg, "far": far, "co_id": co_id, "b1": b1["id"], "b2": b2["id"], "tpl": tpl["id"], "items": tpl["items"]}


async def start(c, ctx, branch="b1", **kw):
    body = {"branch_id": ctx[branch], "template_id": ctx["tpl"], "latitude": LAT, "longitude": LNG, **kw}
    return await c.post(f"{C}/visits", json=body)


def answers(ctx, vals):
    """vals: har band uchun (value|None, na)."""
    return [{"id": i["id"], "value": v, "na": na} for i, (v, na) in zip(ctx["items"], vals, strict=True)]


def test_compute_score_unit():
    a = [
        {"id": "1", "kind": "yesno", "weight": 2, "value": 1, "na": False},
        {"id": "2", "kind": "score", "weight": 3, "value": 4, "na": False},
        {"id": "3", "kind": "yesno", "weight": 5, "value": 0, "na": False, "critical": True},
        {"id": "4", "kind": "yesno", "weight": 1, "value": None, "na": True},
    ]
    score, crit = svc.compute(a)
    assert score == round((2 + 3 * 0.8) / 10 * 100, 1) == 44.0 and crit == 1
    assert svc.compute([{"kind": "yesno", "weight": 1, "value": None, "na": True, "id": "x"}]) == (None, 0)
    assert svc.is_fail({"kind": "score", "value": 1, "na": False}) and not svc.is_fail({"kind": "score", "value": 2, "na": False})


async def test_template_crud_and_validation(new_client, clock):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    assert len(ctx["items"]) == 4 and all(len(i["id"]) == 8 for i in ctx["items"])
    assert (await hr.post(f"{C}/templates", json={"name": "haftalik", "items": ITEMS})).status_code == 409
    assert (await hr.post(f"{C}/templates", json={"name": "X", "items": []})).json()["detail"]["code"] == "items_invalid"
    assert (await ctx["co"].post(f"{C}/templates", json={"name": "Y", "items": ITEMS})).status_code == 403
    assert [t["name"] for t in (await ctx["co"].get(f"{C}/templates")).json()] == ["Haftalik"]
    assert (await ctx["far"].get(f"{C}/templates")).status_code == 403

    r = await hr.put(f"{C}/templates/{ctx['tpl']}", json={"name": "Haftalik", "items": ctx["items"][:2], "is_active": True})
    assert r.status_code == 200 and r.json()["item_count"] == 2 and r.json()["items"][0]["id"] == ctx["items"][0]["id"]  # id saqlanadi
    v = (await start(ctx["co"], ctx)).json()
    assert len(v["answers"]) == 2
    assert (await hr.delete(f"{C}/templates/{ctx['tpl']}")).json()["detail"]["code"] == "template_in_use"
    free = (await hr.post(f"{C}/templates", json={"name": "Bo'sh", "items": ITEMS})).json()
    assert (await hr.delete(f"{C}/templates/{free['id']}")).status_code == 204
    assert (await hr.get("/api/v1/audit", params={"action": "checklists.template_create"})).json()["total"] == 2


async def test_gps_rules(new_client, clock):
    ctx = await setup(new_client)
    far = {"latitude": LAT + 0.01, "longitude": LNG}  # ~1.1 km
    r = await start(ctx["co"], ctx, **far)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "outside_geofence" and r.json()["detail"]["distance"] > 1000
    assert (await ctx["co"].post(f"{C}/visits", json={"branch_id": ctx["b1"], "template_id": ctx["tpl"]})).json()["detail"]["code"] == "coordinates_required"
    r = await start(ctx["co"], ctx, reason="Filial yopiq edi, ko'chada turibman", **far)
    assert r.status_code == 201 and r.json()["geo_ok"] is False and r.json()["geo_reason"]
    await ctx["co"].delete(f"{C}/visits/{r.json()['id']}")
    ok = await start(ctx["co"], ctx)
    assert ok.status_code == 201 and ok.json()["geo_ok"] is True and ok.json()["distance_m"] < 5
    # bir filialga ikkinchi qoralama yo'q
    again = await start(ctx["co"], ctx)
    assert again.status_code == 409 and again.json()["detail"]["id"] == ok.json()["id"]
    # boshqa koordinator filiali, koordinatasiz filial
    assert (await start(ctx["co"], ctx, "b2")).json()["detail"]["code"] == "not_your_branch"
    r = await ctx["co2"].post(f"{C}/visits", json={"branch_id": ctx["b2"], "template_id": ctx["tpl"]})
    assert r.status_code == 201 and r.json()["distance_m"] is None  # koordinatasiz filial: GPS tekshirilmaydi
    assert (await ctx["far"].post(f"{C}/visits", json={"branch_id": ctx["b1"], "template_id": ctx["tpl"]})).status_code == 403
    assert [b["id"] for b in (await ctx["co"].get(f"{C}/branches")).json()] == [ctx["b1"]]
    assert len((await ctx["hr"].get(f"{C}/branches")).json()) == 2


async def test_fill_submit_score_and_notifications(new_client, clock):
    ctx = await setup(new_client)
    v = (await start(ctx["co"], ctx)).json()
    vid = v["id"]
    # tekshiruvlar
    bad = await ctx["co"].put(f"{C}/visits/{vid}/answers", json={"answers": [{"id": ctx["items"][0]["id"], "value": 3}]})
    assert bad.json()["detail"]["code"] == "value_invalid"
    assert (await ctx["co"].put(f"{C}/visits/{vid}/answers", json={"answers": [{"id": "zzz", "value": 1}]})).json()["detail"]["code"] == "unknown_item"
    assert (await ctx["co"].put(f"{C}/visits/{vid}/answers", json={"answers": [{"id": ctx["items"][0]["id"], "na": True}]})).json()["detail"]["code"] == "na_not_allowed"
    # to'liq emas
    await ctx["co"].put(f"{C}/visits/{vid}/answers", json={"answers": answers(ctx, [(1, False), (4, False), (None, False), (None, False)])[:2]})
    r = await ctx["co"].post(f"{C}/visits/{vid}/submit")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unanswered" and r.json()["detail"]["count"] == 1
    # boshqa koordinator ko'ra olmaydi / o'zgartira olmaydi
    assert (await ctx["co2"].get(f"{C}/visits/{vid}")).status_code == 404
    assert (await ctx["mg"].get(f"{C}/visits/{vid}")).status_code == 404  # mudir qoralamani ko'rmaydi

    clock["t"] = NOW + timedelta(hours=1)
    r = await ctx["co"].put(f"{C}/visits/{vid}/answers", json={"answers": answers(ctx, [(1, False), (4, False), (0, False), (None, True)]), "note": "Sertifikat yo'q"})
    assert r.json()["score"] == 44.0 and r.json()["answered"] == 4
    r = await ctx["co"].post(f"{C}/visits/{vid}/submit")
    assert r.status_code == 200 and r.json()["status"] == "submitted" and r.json()["score"] == 44.0 and r.json()["critical_fails"] == 1
    assert r.json()["submitted_at"].startswith("2026-11-10T13:00")
    # bir marta yuboriladi, o'zgarmaydi
    assert (await ctx["co"].post(f"{C}/visits/{vid}/submit")).status_code == 409
    assert (await ctx["co"].put(f"{C}/visits/{vid}/answers", json={"answers": []})).status_code == 409
    assert (await ctx["co"].delete(f"{C}/visits/{vid}")).status_code == 409

    # mudir yuborilganini ko'radi, past ball HR ga xabar
    assert (await ctx["mg"].get(f"{C}/visits/{vid}")).status_code == 200
    mine = (await ctx["mg"].get(f"{C}/visits", params={"scope": "branch"})).json()
    assert mine["total"] == 1
    kinds = lambda c: [n["kind"] for n in c]  # noqa: E731
    mg_notes = (await ctx["mg"].get("/api/v1/notifications")).json()["items"]
    hr_notes = (await ctx["hr"].get("/api/v1/notifications")).json()["items"]
    assert "checklists.submitted" in kinds(mg_notes) and "checklists.low_score" in kinds(hr_notes)
    assert (await ctx["hr"].get("/api/v1/audit", params={"action": "checklists.submit"})).json()["total"] == 1
    assert (await ctx["hr"].get("/api/v1/audit", params={"action": "checklists.start"})).json()["total"] == 1
    # ro'yxat doirasi
    assert (await ctx["co2"].get(f"{C}/visits", params={"scope": "all"})).status_code == 403
    assert (await ctx["hr"].get(f"{C}/visits", params={"scope": "all", "branch_id": ctx["b1"]})).json()["total"] == 1
    assert (await ctx["co"].get(f"{C}/visits")).json()["items"][0]["coordinator"]["name"] == "Coord"


async def test_files_on_draft(new_client, clock):
    ctx = await setup(new_client)
    vid = (await start(ctx["co"], ctx)).json()["id"]
    item = ctx["items"][0]["id"]
    up = await ctx["co"].post(f"{C}/visits/{vid}/files", params={"item_id": item}, files={"file": ("pol.png", b"\x89PNG\r\n\x1a\nxx", "image/png")})
    assert up.status_code == 201, up.text
    assert (await ctx["co"].post(f"{C}/visits/{vid}/files", params={"item_id": "nope"}, files={"file": ("a.png", b"\x89PNG\r\n\x1a\nxx", "image/png")})).json()["detail"]["code"] == "unknown_item"
    assert (await ctx["co"].get(f"{C}/visits/{vid}/files/{up.json()['id']}")).status_code == 200
    assert (await ctx["co2"].get(f"{C}/visits/{vid}/files/{up.json()['id']}")).status_code == 404
    assert len((await ctx["co"].get(f"{C}/visits/{vid}")).json()["files"]) == 1
    assert (await ctx["co"].delete(f"{C}/visits/{vid}/files/{up.json()['id']}")).status_code == 204
    assert (await ctx["co"].delete(f"{C}/visits/{vid}")).status_code == 204
    assert (await ctx["co"].get(f"{C}/visits/{vid}")).status_code == 404


async def do_visit(c, ctx, branch, vals):
    vid = (await start(c, ctx, branch)).json()["id"] if branch == "b1" else (await c.post(f"{C}/visits", json={"branch_id": ctx[branch], "template_id": ctx["tpl"]})).json()["id"]
    await c.put(f"{C}/visits/{vid}/answers", json={"answers": answers(ctx, vals)})
    r = await c.post(f"{C}/visits/{vid}/submit")
    assert r.status_code == 200, r.text
    return r.json()


async def test_coverage_ranking_and_trend(new_client, clock):
    ctx = await setup(new_client)
    full = [(1, False), (5, False), (1, False), (1, True)]  # 100
    half = [(1, False), (0, False), (0, False), (None, True)]  # (2)/(10) = 20 ... pastroq
    clock["t"] = NOW - timedelta(days=20)
    await do_visit(ctx["co"], ctx, "b1", full)
    clock["t"] = NOW - timedelta(days=3)
    await do_visit(ctx["co"], ctx, "b1", half)
    await do_visit(ctx["co2"], ctx, "b2", full)
    clock["t"] = NOW
    s, e = "2026-10-01", "2026-11-30"
    cov = (await ctx["hr"].get(f"{C}/coverage", params={"start": s, "end": e})).json()["items"]
    by = {x["branch"]["id"]: x for x in cov}
    assert by[ctx["b1"]]["visits"] == 2 and by[ctx["b1"]]["days_since"] == 3 and by[ctx["b1"]]["overdue"] is False and by[ctx["b1"]]["last_score"] == 20.0
    assert by[ctx["b1"]]["avg_score"] == 60.0
    # davr tashqarisi: tekshiruv yo'q => muddati o'tgan emas, lekin davrda 0 ta
    narrow = (await ctx["hr"].get(f"{C}/coverage", params={"start": "2026-11-09", "end": "2026-11-10"})).json()["items"]
    assert {x["branch"]["id"]: x["visits"] for x in narrow}[ctx["b1"]] == 0
    clock["t"] = NOW + timedelta(days=20)
    late = (await ctx["hr"].get(f"{C}/coverage", params={"start": s, "end": e, "days": 14})).json()["items"]
    assert all(x["overdue"] for x in late)
    # koordinator faqat o'z filialini ko'radi
    own = (await ctx["co"].get(f"{C}/coverage", params={"start": s, "end": e})).json()["items"]
    assert [x["branch"]["id"] for x in own] == [ctx["b1"]]
    rk = (await ctx["hr"].get(f"{C}/ranking", params={"start": s, "end": e})).json()
    assert [b["id"] for b in rk["branches"]] == [ctx["b2"], ctx["b1"]] and rk["branches"][0]["avg_score"] == 100.0
    assert rk["coordinators"][0]["visits"] == 2 and rk["coordinators"][0]["branches"] == 1
    assert len((await ctx["co2"].get(f"{C}/ranking", params={"start": s, "end": e})).json()["branches"]) == 1
    tr = (await ctx["hr"].get(f"{C}/trend", params={"start": s, "end": e, "branch_id": ctx["b1"]})).json()
    assert [t["visits"] for t in tr] == [1, 1] and [t["avg_score"] for t in tr] == [100.0, 20.0]
    assert datetime.fromisoformat(tr[0]["week"]).weekday() == 0
    assert (await ctx["hr"].get(f"{C}/trend", params={"start": "2020-01-01", "end": "2026-11-30"})).status_code == 400
