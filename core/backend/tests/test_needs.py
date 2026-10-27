from datetime import datetime, timedelta

import pytest

from app.db import SessionLocal
from app.services import needs as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

N = "/api/v1/needs"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=tz())


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    fn = lambda: state["t"]  # noqa: E731
    for mod in ("app.api.needs", "app.services.needs"):
        monkeypatch.setattr(f"{mod}.now", fn)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def setup(new_client):
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    req, req_id = await as_user(new_client, "ali", "farmasevt")
    other, other_id = await as_user(new_client, "bob", "farmasevt")
    it, it_id = await as_user(new_client, "it", "ayti")
    return {"hr": hr, "hr_id": hr_id, "req": req, "req_id": req_id, "other": other, "other_id": other_id, "it": it, "it_id": it_id}


async def mk(c, title="Printer kerak", **kw):
    r = await c.post(N, json={"title": title, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def kinds(c):
    return [n["kind"] for n in (await c.get("/api/v1/notifications")).json()["items"]]


async def test_full_four_stage_flow_and_audit(new_client, clock):
    ctx = await setup(new_client)
    n = await mk(ctx["req"], description="Filialga")
    assert n["status"] == "requested" and n["number"] == "E-2026-0001" and n["assignee"] is None
    assert "needs.new" in await kinds(ctx["hr"])

    # begona foydalanuvchi ko'rmaydi, so'rovchi ijrochi tayinlay olmaydi
    assert (await ctx["other"].get(f"{N}/{n['id']}")).status_code == 404
    assert (await ctx["req"].post(f"{N}/{n['id']}/assign", json={"assignee_id": ctx["it_id"]})).status_code == 403
    # ijrochi bo'la olmaydigan foydalanuvchi
    r = await ctx["hr"].post(f"{N}/{n['id']}/assign", json={"assignee_id": ctx["other_id"]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_assignee"

    r = await ctx["hr"].post(f"{N}/{n['id']}/assign", json={"assignee_id": ctx["it_id"], "note": "Tezroq"})
    assert r.status_code == 200 and r.json()["status"] == "assigned"
    assert "needs.assigned" in await kinds(ctx["it"]) and "needs.assigned_requester" in await kinds(ctx["req"])

    # faqat ijrochi bajaradi
    assert (await ctx["hr"].post(f"{N}/{n['id']}/complete", json={"report": "tayyor"})).status_code == 403
    assert (await ctx["it"].post(f"{N}/{n['id']}/complete", json={"report": "x"})).status_code == 422
    clock["t"] = NOW + timedelta(hours=5)
    r = await ctx["it"].post(f"{N}/{n['id']}/complete", json={"report": "Printer o'rnatildi"})
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert "needs.completed" in await kinds(ctx["req"])

    # ijrochi o'zi tasdiqlay olmaydi; so'rovchi tasdiqlaydi
    assert (await ctx["it"].post(f"{N}/{n['id']}/confirm", json={"rating": 5})).status_code == 403
    assert (await ctx["req"].post(f"{N}/{n['id']}/confirm", json={"rating": 9})).status_code == 422
    r = await ctx["req"].post(f"{N}/{n['id']}/confirm", json={"rating": 5, "note": "Rahmat"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed" and r.json()["rating"] == 5
    assert "needs.confirmed" in await kinds(ctx["it"])

    # yakunlangandan keyin o'zgarmaydi
    assert (await ctx["req"].post(f"{N}/{n['id']}/cancel", json={"note": "kerakmas"})).status_code == 409
    assert (await ctx["it"].post(f"{N}/{n['id']}/complete", json={"report": "yana"})).status_code == 409

    d = (await ctx["req"].get(f"{N}/{n['id']}")).json()
    assert [e["action"] for e in d["events"]] == ["requested", "assigned", "completed", "confirmed"]
    assert d["report"] == "Printer o'rnatildi" and d["can"]["edit"] is False

    # har bosqich auditda
    for a in ("request", "assign", "complete", "confirm"):
        assert (await ctx["hr"].get("/api/v1/audit", params={"action": f"needs.{a}"})).json()["total"] == 1, a


async def test_return_and_cancel(new_client, clock):
    ctx = await setup(new_client)
    n = await mk(ctx["req"])
    await ctx["hr"].post(f"{N}/{n['id']}/assign", json={"assignee_id": ctx["it_id"]})
    await ctx["it"].post(f"{N}/{n['id']}/complete", json={"report": "Bajarildi"})
    r = await ctx["req"].post(f"{N}/{n['id']}/return", json={"note": "x"})
    assert r.status_code == 422
    r = await ctx["req"].post(f"{N}/{n['id']}/return", json={"note": "Hali ishlamayapti"})
    assert r.status_code == 200 and r.json()["status"] == "assigned" and r.json()["return_count"] == 1
    assert "needs.returned" in await kinds(ctx["it"])
    await ctx["it"].post(f"{N}/{n['id']}/complete", json={"report": "Tuzatildi"})
    assert (await ctx["req"].post(f"{N}/{n['id']}/confirm", json={})).json()["rating"] is None

    m = await mk(ctx["req"], "Boshqa")
    assert (await ctx["other"].post(f"{N}/{m['id']}/cancel", json={"note": "bekor"})).status_code == 404
    r = await ctx["req"].post(f"{N}/{m['id']}/cancel", json={"note": "Endi kerakmas"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert (await ctx["hr"].post(f"{N}/{m['id']}/assign", json={"assignee_id": ctx["it_id"]})).status_code == 409
    assert (await ctx["hr"].get("/api/v1/audit", params={"action": "needs.cancel"})).json()["total"] == 1


async def test_update_rules_scopes_and_filters(new_client, clock):
    ctx = await setup(new_client)
    n = await mk(ctx["req"], "Eski nom")
    r = await ctx["req"].put(f"{N}/{n['id']}", json={"title": "Yangi nom", "priority": "high"})
    assert r.status_code == 200 and r.json()["title"] == "Yangi nom" and r.json()["priority"] == "high"
    assert (await ctx["other"].put(f"{N}/{n['id']}", json={"title": "Buzish"})).status_code == 404
    await ctx["hr"].post(f"{N}/{n['id']}/assign", json={"assignee_id": ctx["it_id"]})
    assert (await ctx["req"].put(f"{N}/{n['id']}", json={"title": "Yana"})).status_code == 403  # tayinlangach faqat dispetcher
    assert (await ctx["hr"].put(f"{N}/{n['id']}", json={"title": "Dispetcher"})).status_code == 200

    await mk(ctx["other"], "Bobning")
    mine = (await ctx["req"].get(N)).json()
    assert mine["total"] == 1
    assert (await ctx["it"].get(N, params={"scope": "assigned"})).json()["total"] == 1
    assert (await ctx["req"].get(N, params={"scope": "all"})).status_code == 403
    assert (await ctx["hr"].get(N, params={"scope": "all"})).json()["total"] == 2
    assert (await ctx["hr"].get(N, params={"scope": "all", "status": "requested"})).json()["total"] == 1
    assert (await ctx["hr"].get(N, params={"scope": "all", "q": "E-2026-0002"})).json()["total"] == 1
    s = (await ctx["it"].get(f"{N}/summary")).json()
    assert s["todo"] == 1 and s["unassigned"] == 0
    assert (await ctx["hr"].get(f"{N}/summary")).json()["unassigned"] == 1


async def test_categories_auto_assign_and_sla(new_client, clock):
    ctx = await setup(new_client)
    r = await ctx["hr"].post(f"{N}/categories", json={"name": "IT", "sla_days": 2, "default_assignee_id": ctx["it_id"]})
    assert r.status_code == 201, r.text
    cat = r.json()
    assert (await ctx["hr"].post(f"{N}/categories", json={"name": "it"})).status_code == 409
    assert (await ctx["hr"].post(f"{N}/categories", json={"name": "Z", "default_assignee_id": ctx["other_id"]})).json()["detail"]["code"] == "unknown_assignee"
    assert (await ctx["req"].post(f"{N}/categories", json={"name": "Q"})).status_code == 403
    assert any(c["id"] == cat["id"] for c in (await ctx["req"].get(f"{N}/categories")).json())

    n = await mk(ctx["req"], category_id=cat["id"])
    assert n["status"] == "assigned" and n["assignee"]["id"] == ctx["it_id"]
    assert datetime.fromisoformat(n["due_at"]) == NOW + timedelta(days=2)
    d = (await ctx["req"].get(f"{N}/{n['id']}")).json()
    assert d["events"][1]["action"] == "assigned" and d["events"][1]["data"]["auto"] is True
    assert "needs.assigned" in await kinds(ctx["it"])

    assert (await ctx["hr"].delete(f"{N}/categories/{cat['id']}")).json()["detail"]["code"] == "category_in_use"
    r = await ctx["hr"].put(f"{N}/categories/{cat['id']}", json={"name": "IT", "is_active": False})
    assert r.status_code == 200
    assert (await ctx["req"].post(N, json={"title": "Yana", "category_id": cat["id"]})).json()["detail"]["code"] == "unknown_category"
    free = (await ctx["hr"].post(f"{N}/categories", json={"name": "Bo'sh"})).json()
    assert (await ctx["hr"].delete(f"{N}/categories/{free['id']}")).status_code == 204


async def test_deadlines_notify_once_and_audit(new_client, clock):
    ctx = await setup(new_client)
    n = await mk(ctx["req"], due_at=(NOW + timedelta(hours=30)).isoformat())
    await ctx["hr"].post(f"{N}/{n['id']}/assign", json={"assignee_id": ctx["it_id"]})
    async with SessionLocal() as s:
        assert (await svc.check_deadlines(s, NOW))[:2] == (0, 0)
        soon, late, _ = await svc.check_deadlines(s, NOW + timedelta(hours=10))
        assert (soon, late) == (1, 0)
        assert (await svc.check_deadlines(s, NOW + timedelta(hours=11)))[:2] == (0, 0)  # takror yuborilmaydi
        _, late, _ = await svc.check_deadlines(s, NOW + timedelta(hours=31))
        assert late == 1
        await s.commit()
    assert {"needs.due_soon", "needs.overdue"} <= set(await kinds(ctx["it"]))
    assert (await ctx["hr"].get("/api/v1/audit", params={"action": "needs.overdue"})).json()["total"] == 1
    clock["t"] = NOW + timedelta(hours=31)
    d = (await ctx["req"].get(f"{N}/{n['id']}")).json()
    assert d["overdue"] is True and d["events"][-1]["action"] == "overdue"
    assert (await ctx["hr"].get(N, params={"scope": "all", "overdue": "true"})).json()["total"] == 1

    # bajarilgan ehtiyoj muddat nazoratidan chiqadi
    m = await mk(ctx["req"], "Ikkinchi", due_at=(NOW + timedelta(hours=1)).isoformat())
    await ctx["hr"].post(f"{N}/{m['id']}/assign", json={"assignee_id": ctx["it_id"]})
    await ctx["it"].post(f"{N}/{m['id']}/complete", json={"report": "Tayyor"})
    async with SessionLocal() as s:
        assert (await svc.check_deadlines(s, NOW + timedelta(days=5)))[1] == 0
        await s.rollback()


async def test_comments_files_and_analytics(new_client, clock):
    ctx = await setup(new_client)
    n = await mk(ctx["req"])
    await ctx["hr"].post(f"{N}/{n['id']}/assign", json={"assignee_id": ctx["it_id"]})
    r = await ctx["it"].post(f"{N}/{n['id']}/comments", json={"body": "Ertaga olib kelaman"})
    assert r.status_code == 201
    assert "needs.comment" in await kinds(ctx["req"])
    assert (await ctx["other"].post(f"{N}/{n['id']}/comments", json={"body": "x"})).status_code == 404
    assert len((await ctx["req"].get(f"{N}/{n['id']}/comments")).json()) == 1

    up = await ctx["req"].post(f"{N}/{n['id']}/files", files={"file": ("chek.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert up.status_code == 201, up.text
    fid = up.json()["id"]
    assert (await ctx["it"].get(f"{N}/{n['id']}/files/{fid}")).status_code == 200
    assert (await ctx["it"].delete(f"{N}/{n['id']}/files/{fid}")).status_code == 403
    assert (await ctx["req"].delete(f"{N}/{n['id']}/files/{fid}")).status_code == 204
    assert (await ctx["req"].get(f"{N}/{n['id']}")).json()["comments"] == 1

    clock["t"] = NOW + timedelta(hours=4)
    await ctx["it"].post(f"{N}/{n['id']}/complete", json={"report": "Bajarildi"})
    await ctx["req"].post(f"{N}/{n['id']}/confirm", json={"rating": 4})
    day = NOW.date().isoformat()
    a = (await ctx["hr"].get(f"{N}/analytics", params={"start": day, "end": day, "scope": "all"})).json()
    k = a["kpis"]
    assert k["created"] == 1 and k["completed"] == 1 and k["confirmed"] == 1 and k["avg_rating"] == 4.0 and k["avg_hours"] == 4.0
    assert a["by_status"]["confirmed"] == 1 and a["trend"][0] == {"date": day, "created": 1, "completed": 1}
    assert a["by_executor"][0]["name"] == "It" and a["by_executor"][0]["done"] == 1
    assert (await ctx["req"].get(f"{N}/analytics", params={"start": day, "end": day, "scope": "all"})).status_code == 403
    assert (await ctx["req"].get(f"{N}/analytics", params={"start": day, "end": day})).json()["kpis"]["created"] == 1
    assert (await ctx["hr"].get(f"{N}/analytics", params={"start": "2026-01-01", "end": "2026-12-31"})).status_code == 400
