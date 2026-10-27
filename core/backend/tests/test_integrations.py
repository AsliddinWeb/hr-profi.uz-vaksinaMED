from datetime import date, timedelta

from app import plans
from app.db import SessionLocal
from app.models.employees import Employee
from app.models.org import Branch, Position
from tests.conftest import login, make_user

IT = "/api/v1/integrations"
EXT = "/api/ext/v1"
CP = "/api/v1/complaints"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


async def setup(new_client):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    hr, _ = await as_user(new_client, "hrm", "hr_menejer")
    far, far_uid = await as_user(new_client, "far", "farmasevt")
    b1 = (await hrd.post("/api/v1/branches", json={"number": 71, "name": "Chilonzor-1"})).json()
    await hrd.post("/api/v1/branches", json={"number": 72, "name": "Yunusobod"})
    async with SessionLocal() as s:
        p = Position(name="Farmasevt")
        s.add(p)
        await s.flush()
        s.add(Employee(last_name="Far", first_name="X", full_name="Far X", user_id=far_uid, status="active", branch_id=b1["id"], position_id=p.id, hire_date=date(2026, 1, 1)))
        await s.commit()
        # 71-filialning me'yori 2 farmatsevt, hozir 1 ta: xodim yetishmaydi
        br = await s.get(Branch, b1["id"])
        br.staff_norm = {"manager": 0, "pharmacist": 2, "intern": 0}
        await s.commit()
    return {"hrd": hrd, "hr": hr, "far": far}


async def test_api_keys_scopes_and_metrics_ingest(new_client):
    ctx = await setup(new_client)
    assert (await ctx["hr"].post(f"{IT}/keys", json={"name": "Dori", "scopes": ["metrics:write"]})).status_code == 403  # faqat HRD
    assert (await ctx["hrd"].post(f"{IT}/keys", json={"name": "Dori", "scopes": ["bad"]})).json()["detail"]["code"] == "scope_invalid"
    k = (await ctx["hrd"].post(f"{IT}/keys", json={"name": "Dori", "scopes": ["metrics:write", "branches:read"]})).json()
    key = k["key"]
    assert key.startswith("koshi_") and "key" not in (await ctx["hrd"].get(f"{IT}/keys")).json()[0]

    ext = new_client()
    ext.headers["X-API-Key"] = key
    ext.headers.pop("X-Requested-With", None)  # tashqi tizim cookie/CSRF headersiz ishlaydi
    today = date.today()
    items = [
        {"branch_number": 71, "date": str(today), "sales": "12000000.50", "plan": "20000000", "receipts": 150},
        {"branch_number": 72, "date": str(today), "sales": 30000000, "plan": 25000000},
        {"branch_number": 999, "date": str(today), "sales": 1},
    ]
    r = await ext.post(f"{EXT}/metrics/daily", json={"items": items})
    assert r.status_code == 200 and r.json() == {"saved": 2, "unknown_branches": [999]}
    assert (await ext.post(f"{EXT}/metrics/daily", json={"items": items[:1]})).json()["saved"] == 1  # takror: yangilanadi
    assert (await ext.get(f"{EXT}/branches")).status_code == 200
    assert (await ext.get(f"{EXT}/employees")).json()["detail"]["code"] == "scope_forbidden"  # scope yo'q
    bad = new_client()
    bad.headers["X-API-Key"] = "koshi_abcd1234_" + "x" * 30
    assert (await bad.get(f"{EXT}/branches")).status_code == 401
    assert (await new_client().get(f"{EXT}/branches")).status_code == 401
    assert (await ctx["hrd"].post(f"{EXT}/metrics/daily", json={"items": items[:1]})).status_code == 401  # kalitsiz (cookie bilan) ruxsat yo'q
    fut = await ext.post(f"{EXT}/metrics/daily", json={"items": [{**items[0], "date": str(today + timedelta(days=30))}]})
    assert fut.json()["detail"]["code"] == "date_future"

    # hisobot: reja past + xodim yetishmaydigan filial xavfli deb belgilanadi
    rep = (await ctx["hr"].get(f"{IT}/metrics", params={"start": str(today - timedelta(days=7)), "end": str(today)})).json()
    first = rep["items"][0]
    assert first["branch"]["number"] == 71 and first["attainment"] == 60.0 and first["staff_gaps"] == {"pharmacist": 1} and first["at_risk"] is True
    assert rep["items"][1]["attainment"] == 120.0 and rep["items"][1]["at_risk"] is False
    assert (await ctx["far"].get(f"{IT}/metrics", params={"start": str(today), "end": str(today)})).status_code == 403

    # kalitni bekor qilsak ishlamaydi; xodimlar ro'yxatida maxfiy maydon yo'q
    k2 = (await ctx["hrd"].post(f"{IT}/keys", json={"name": "HR", "scopes": ["employees:read"]})).json()
    ext2 = new_client()
    ext2.headers["X-API-Key"] = k2["key"]
    emp = (await ext2.get(f"{EXT}/employees", params={"branch_number": 71})).json()["items"]
    assert emp and set(emp[0]) == {"employee_no", "full_name", "position", "branch_number", "hire_date"}
    await ctx["hrd"].post(f"{IT}/keys/{k2['id']}/revoke")
    assert (await ext2.get(f"{EXT}/employees")).status_code == 401


async def test_keys_need_premium_plan(new_client, app):
    ctx = await setup(new_client)
    cfg = app.state.client_config
    before = cfg.plan
    try:
        cfg.plan = "pro"
        plans.configure("pro", {})
        r = await ctx["hrd"].post(f"{IT}/keys", json={"name": "Xy", "scopes": ["branches:read"]})
        assert r.status_code == 403 and r.json()["detail"]["code"] == "plan_feature"
    finally:
        cfg.plan = before
        plans.configure(before, cfg.license)


async def test_branch_reconcile(new_client):
    ctx = await setup(new_client)
    rows = [
        {"number": 71, "name": "Chilonzor-1"},  # mos
        {"number": 72, "name": "Yunusabad"},  # nomi farq qiladi
        {"number": 500, "name": "Yangi filial"},  # tizimda yo'q
        {"number": 500, "name": "Yangi filial (qayta)"},  # takror raqam
        {"name": "chilonzor 1"},  # raqamsiz: nom bo'yicha topiladi
    ]
    r = (await ctx["hr"].post(f"{IT}/reconcile", json={"rows": rows})).json()
    assert r["external_total"] == 5 and r["system_total"] == 2 and r["matched"] == 2
    assert r["mismatch"][0]["number"] == 72 and r["mismatch"][0]["kind"] == "name"
    assert [x["number"] for x in r["only_external"]] == [500, 500] and r["duplicates_external"] == [500] and r["only_system"] == []
    assert (await ctx["far"].post(f"{IT}/reconcile", json={"rows": rows})).status_code == 403


async def test_complaints_flow_and_anonymity(new_client):
    ctx = await setup(new_client)
    body = {"category": "manager", "title": "Mudir haqida", "text": "Smena jadvali adolatsiz", "is_anonymous": True}
    r = await ctx["far"].post(CP, json=body)
    assert r.status_code == 201 and r.json()["author"] == "Far"
    cid = r.json()["id"]
    assert any(n["kind"] == "complaint.new" for n in await notes(ctx["hr"]))
    # HR anonim muallifni ko'rmaydi; boshqa xodim shikoyatni ko'ra olmaydi
    seen = (await ctx["hr"].get(f"{CP}/{cid}")).json()
    assert seen["author"] is None and seen["history"][0]["actor"] is None and seen["can_handle"]
    assert (await ctx["far"].get(f"{CP}", params={"scope": "inbox"})).status_code == 403
    other, _ = await as_user(new_client, "other", "farmasevt")
    assert (await other.get(f"{CP}/{cid}")).status_code == 404
    assert len((await ctx["hr"].get(CP, params={"scope": "inbox"})).json()) == 1 and (await ctx["hr"].get(CP, params={"scope": "mine"})).json() == []

    assert (await ctx["hr"].post(f"{CP}/{cid}/take")).json()["status"] == "in_progress"
    assert (await ctx["far"].post(f"{CP}/{cid}/answer", json={"action": "resolve", "response": "Yaxshi"})).status_code == 403
    assert (await ctx["hr"].post(f"{CP}/{cid}/answer", json={"action": "resolve", "response": ""})).status_code == 422
    r = await ctx["hr"].post(f"{CP}/{cid}/answer", json={"action": "resolve", "response": "Jadval qayta ko'rib chiqildi"})
    assert r.json()["status"] == "resolved" and r.json()["author"] is None
    mine = (await ctx["far"].get(CP, params={"scope": "mine"})).json()
    assert mine[0]["status"] == "resolved" and mine[0]["response"].startswith("Jadval")
    assert any(n["kind"] == "complaint.answer" for n in await notes(ctx["far"]))
    assert (await ctx["hr"].post(f"{CP}/{cid}/answer", json={"action": "reject", "response": "yana"})).json()["detail"]["code"] == "already_decided"

    # anonim bo'lmagan shikoyatda HR muallifni ko'radi
    r = await ctx["far"].post(CP, json={**body, "is_anonymous": False})
    assert (await ctx["hr"].get(f"{CP}/{r.json()['id']}")).json()["author"] == "Far"
