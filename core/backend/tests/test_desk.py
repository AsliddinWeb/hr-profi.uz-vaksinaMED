from datetime import datetime, timedelta

import pytest

from app.db import SessionLocal
from app.services import helpdesk, reception
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

H = "/api/v1/helpdesk"
R = "/api/v1/reception"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=tz())


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    fn = lambda: state["t"]  # noqa: E731
    for mod in ("app.api.helpdesk", "app.services.helpdesk", "app.api.reception", "app.services.reception"):
        monkeypatch.setattr(f"{mod}.now", fn, raising=False)
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
    desk, desk_id = await as_user(new_client, "desk", "resepshin")
    return {"hr": hr, "hr_id": hr_id, "req": req, "req_id": req_id, "other": other, "other_id": other_id, "it": it, "it_id": it_id, "desk": desk, "desk_id": desk_id}


async def kinds(c):
    return [n["kind"] for n in (await c.get("/api/v1/notifications")).json()["items"]]


async def mk(c, title="Printer ishlamayapti", **kw):
    r = await c.post(H, json={"title": title, **kw})
    assert r.status_code == 201, r.text
    return r.json()


# --- AyTi ------------------------------------------------------------------------------


async def test_ticket_flow_take_wait_resolve_close(new_client, clock):
    ctx = await setup(new_client)
    t = await mk(ctx["req"], priority="high")
    assert t["status"] == "new" and t["number"] == "T-2026-0001"
    assert datetime.fromisoformat(t["due_at"]) - NOW == timedelta(hours=8)
    assert "helpdesk.new" in await kinds(ctx["it"])

    # begona ko'rmaydi; oddiy foydalanuvchi olmaydi
    assert (await ctx["other"].get(f"{H}/{t['id']}")).status_code == 404
    assert (await ctx["req"].post(f"{H}/{t['id']}/take")).status_code == 403

    clock["t"] = NOW + timedelta(minutes=10)
    r = await ctx["it"].post(f"{H}/{t['id']}/take")
    assert r.status_code == 200 and r.json()["status"] == "in_progress" and r.json()["assignee"]["id"] == ctx["it_id"]
    assert r.json()["first_response_at"] is not None
    assert "helpdesk.taken" in await kinds(ctx["req"])
    # ikkinchi marta olib bo'lmaydi
    assert (await ctx["it"].post(f"{H}/{t['id']}/take")).status_code in (403, 409)

    r = await ctx["it"].post(f"{H}/{t['id']}/wait", json={"note": "Model raqamini yuboring"})
    assert r.json()["status"] == "waiting" and "helpdesk.waiting" in await kinds(ctx["req"])
    assert (await ctx["it"].post(f"{H}/{t['id']}/resume")).json()["status"] == "in_progress"

    # so'rovchi hal qila olmaydi
    assert (await ctx["req"].post(f"{H}/{t['id']}/resolve", json={"resolution": "tayyor"})).status_code == 403
    r = await ctx["it"].post(f"{H}/{t['id']}/resolve", json={"resolution": "Drayver qayta o'rnatildi"})
    assert r.json()["status"] == "resolved" and not r.json()["sla_breached"]
    assert "helpdesk.resolved" in await kinds(ctx["req"])

    r = await ctx["req"].post(f"{H}/{t['id']}/close", json={"rating": 5, "comment": "Rahmat"})
    assert r.json()["status"] == "closed" and r.json()["rating"] == 5

    d = (await ctx["req"].get(f"{H}/{t['id']}")).json()
    assert [e["to_status"] for e in d["events"] if e["action"] == "status"] == ["in_progress", "waiting", "in_progress", "resolved", "closed"]


async def test_ticket_reopen_assign_cancel_and_internal_notes(new_client, clock):
    ctx = await setup(new_client)
    t = await mk(ctx["req"])
    # menejer tayinlaydi
    assert (await ctx["req"].post(f"{H}/{t['id']}/assign", json={"assignee_id": ctx["it_id"]})).status_code == 403
    r = await ctx["hr"].post(f"{H}/{t['id']}/assign", json={"assignee_id": ctx["other_id"]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_assignee"
    r = await ctx["hr"].post(f"{H}/{t['id']}/assign", json={"assignee_id": ctx["it_id"]})
    assert r.json()["status"] == "in_progress" and "helpdesk.assigned" in await kinds(ctx["it"])

    # ichki izoh so'rovchiga ko'rinmaydi
    assert (await ctx["req"].post(f"{H}/{t['id']}/comments", json={"body": "ichki", "internal": True})).status_code == 403
    assert (await ctx["it"].post(f"{H}/{t['id']}/comments", json={"body": "yashirin", "internal": True})).status_code == 201
    assert (await ctx["it"].post(f"{H}/{t['id']}/comments", json={"body": "ochiq javob"})).status_code == 201
    req_view = [e["note"] for e in (await ctx["req"].get(f"{H}/{t['id']}")).json()["events"] if e["action"] == "comment"]
    it_view = [e["note"] for e in (await ctx["it"].get(f"{H}/{t['id']}")).json()["events"] if e["action"] == "comment"]
    assert req_view == ["ochiq javob"] and it_view == ["yashirin", "ochiq javob"]

    await ctx["it"].post(f"{H}/{t['id']}/resolve", json={"resolution": "tuzatildi"})
    assert (await ctx["other"].post(f"{H}/{t['id']}/reopen", json={"note": "yana"})).status_code == 404
    r = await ctx["req"].post(f"{H}/{t['id']}/reopen", json={"note": "Yana buzildi"})
    assert r.json()["status"] == "in_progress" and r.json()["reopen_count"] == 1 and r.json()["resolved_at"] is None

    # bekor qilish faqat ochiq holatda
    t2 = await mk(ctx["req"], title="Parol tiklash")
    assert (await ctx["req"].post(f"{H}/{t2['id']}/cancel", json={"note": "x"})).status_code == 422
    r = await ctx["req"].post(f"{H}/{t2['id']}/cancel", json={"note": "Kerak emas"})
    assert r.json()["status"] == "cancelled"
    assert (await ctx["req"].post(f"{H}/{t2['id']}/comments", json={"body": "salom"})).status_code == 409


async def test_ticket_category_auto_assign_scopes_and_edit(new_client, clock):
    ctx = await setup(new_client)
    r = await ctx["hr"].post(f"{H}/categories", json={"name": "Kassa", "default_assignee_id": ctx["it_id"]})
    assert r.status_code == 201, r.text
    cat = r.json()
    assert (await ctx["hr"].post(f"{H}/categories", json={"name": "kassa"})).status_code == 409
    assert (await ctx["req"].post(f"{H}/categories", json={"name": "Yangi"})).status_code == 403

    t = await mk(ctx["req"], category_id=cat["id"])
    assert t["assignee"]["id"] == ctx["it_id"] and t["status"] == "new"
    assert "helpdesk.assigned" in await kinds(ctx["it"])
    # navbat (queue) — tayinlanmaganlar
    t2 = await mk(ctx["req"], title="Ikkinchi")
    q = (await ctx["it"].get(H, params={"scope": "queue"})).json()
    assert [x["id"] for x in q["items"]] == [t2["id"]]
    assert (await ctx["req"].get(H, params={"scope": "all"})).status_code == 403
    assert (await ctx["req"].get(H, params={"scope": "queue"})).status_code == 403
    mine = (await ctx["req"].get(H)).json()
    assert mine["total"] == 2 and (await ctx["other"].get(H)).json()["total"] == 0

    # tahrirlash: faqat new holatida; prioritet SLA ni qayta hisoblaydi
    r = await ctx["req"].put(f"{H}/{t2['id']}", json={"title": "Ikkinchi ticket", "priority": "urgent"})
    assert r.status_code == 200 and datetime.fromisoformat(r.json()["due_at"]) - NOW == timedelta(hours=4)
    await ctx["it"].post(f"{H}/{t2['id']}/take")
    assert (await ctx["req"].put(f"{H}/{t2['id']}", json={"title": "Uchinchi ticket"})).status_code == 409

    # kategoriya ishlatilgan bo'lsa o'chirilmaydi
    assert (await ctx["hr"].delete(f"{H}/categories/{cat['id']}")).status_code == 409
    c2 = (await ctx["hr"].post(f"{H}/categories", json={"name": "Vaqtincha"})).json()
    assert (await ctx["hr"].delete(f"{H}/categories/{c2['id']}")).status_code == 204


async def test_ticket_sla_watch_autoclose_and_analytics(new_client, clock):
    ctx = await setup(new_client)
    t = await mk(ctx["req"], priority="urgent")  # 4 soat
    t2 = await mk(ctx["req"], title="Eski hal qilingan")
    await ctx["it"].post(f"{H}/{t2['id']}/take")
    await ctx["it"].post(f"{H}/{t2['id']}/resolve", json={"resolution": "ok ok"})

    late_time = NOW + timedelta(hours=5)
    async with SessionLocal() as db:
        late, closed, notes = await helpdesk.watch(db, late_time)
        await db.commit()
    assert (late, closed) == (1, 0) and notes
    d = (await ctx["it"].get(f"{H}/{t['id']}")).json()
    assert d["sla_breached"] and any(e["action"] == "sla" for e in d["events"])
    # qayta ishga tushganda takror xabar yo'q
    async with SessionLocal() as db:
        assert (await helpdesk.watch(db, late_time))[0] == 0

    async with SessionLocal() as db:
        late, closed, _ = await helpdesk.watch(db, NOW + timedelta(hours=80))
        await db.commit()
    assert closed == 1
    assert (await ctx["it"].get(f"{H}/{t2['id']}")).json()["status"] == "closed"

    clock["t"] = NOW + timedelta(hours=80)
    a = (await ctx["hr"].get(f"{H}/analytics", params={"start": "2026-11-01", "end": "2026-11-30"})).json()
    assert a["kpis"]["created"] == 2 and a["kpis"]["resolved"] == 1 and a["kpis"]["overdue"] == 1
    assert a["by_status"]["closed"] == 1 and a["by_priority"]["urgent"] == 1
    assert (await ctx["req"].get(f"{H}/analytics", params={"start": "2026-11-01", "end": "2026-11-30"})).status_code == 403


async def test_ticket_files(new_client, clock):
    ctx = await setup(new_client)
    t = await mk(ctx["req"])
    r = await ctx["req"].post(f"{H}/{t['id']}/files", files={"file": ("ekran.png", b"\x89PNG\r\n\x1a\n" + b"0" * 40, "image/png")})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    assert (await ctx["other"].get(f"{H}/{t['id']}/files/{fid}")).status_code == 404
    got = await ctx["it"].get(f"{H}/{t['id']}/files/{fid}")
    assert got.status_code == 200 and got.content.startswith(b"\x89PNG")
    assert (await ctx["it"].delete(f"{H}/{t['id']}/files/{fid}")).status_code == 403
    assert (await ctx["req"].delete(f"{H}/{t['id']}/files/{fid}")).status_code == 204
    assert (await ctx["req"].get(f"{H}/{t['id']}")).json()["files"] == 0


# --- Resepshin -------------------------------------------------------------------------


async def mk_emp(_c, name="Karim Host", user_id=None):
    from app.models.employees import Employee

    async with SessionLocal() as db:
        e = Employee(last_name="Host", first_name="Karim", full_name=name, user_id=user_id, status="active")
        db.add(e)
        await db.commit()
        return e.id


async def test_visit_prebook_arrive_leave(new_client, clock):
    ctx = await setup(new_client)
    host_emp = await mk_emp(ctx, user_id=ctx["req_id"])
    exp = (NOW + timedelta(hours=1)).isoformat()
    # oddiy xodim: oldindan yozadi (kelish vaqti shart)
    r = await ctx["req"].post(R, json={"visitor_name": "Anvar Aliyev", "host_id": host_emp})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "expected_required"
    r = await ctx["req"].post(R, json={"visitor_name": "Anvar Aliyev", "host_id": host_emp, "expected_at": exp, "purpose": "meeting"})
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["status"] == "expected"
    # begona ko'rmaydi, oddiy xodim kirishni belgilay olmaydi
    assert (await ctx["other"].get(f"{R}/{v['id']}")).status_code == 404
    assert (await ctx["req"].post(f"{R}/{v['id']}/arrive", json={})).status_code == 403
    assert (await ctx["req"].get(R, params={"scope": "all"})).status_code == 403

    clock["t"] = NOW + timedelta(hours=1)
    r = await ctx["desk"].post(f"{R}/{v['id']}/arrive", json={"badge_no": "17"})
    assert r.status_code == 200 and r.json()["status"] == "arrived" and r.json()["inside"] and r.json()["badge_no"] == "17"
    assert "reception.arrived" in await kinds(ctx["req"])
    assert (await ctx["desk"].post(f"{R}/{v['id']}/arrive", json={})).status_code == 409
    assert (await ctx["desk"].get(f"{R}/summary")).json()["inside"] == 1

    clock["t"] = NOW + timedelta(hours=2)
    r = await ctx["desk"].post(f"{R}/{v['id']}/leave")
    assert r.json()["status"] == "left" and r.json()["left_at"]
    assert (await ctx["desk"].post(f"{R}/{v['id']}/leave")).status_code == 409
    rep = (await ctx["desk"].get(f"{R}/report", params={"start": "2026-11-01", "end": "2026-11-30"})).json()
    assert rep["total"] == 1 and rep["avg_minutes"] == 60.0 and rep["by_purpose"]["meeting"] == 1 and rep["inside_now"] == 0


async def test_visit_walk_in_edit_cancel_no_show(new_client, clock):
    ctx = await setup(new_client)
    # resepshin to'g'ridan-to'g'ri keldi deb yozadi
    r = await ctx["desk"].post(R, json={"visitor_name": "Kuryer Bobur", "purpose": "delivery", "arrive": True, "vehicle_plate": "01A123BC"})
    assert r.status_code == 201 and r.json()["status"] == "arrived"
    # oddiy xodim "arrive" qila olmaydi
    assert (await ctx["req"].post(R, json={"visitor_name": "Soxta", "arrive": True})).status_code == 403

    r = await ctx["desk"].put(f"{R}/{r.json()['id']}", json={"visitor_name": "Kuryer Bobur", "purpose": "delivery", "vehicle_plate": "01B777CD", "note": "Dori yetkazdi"})
    assert r.status_code == 200 and r.json()["vehicle_plate"] == "01B777CD"

    exp = (NOW + timedelta(hours=1)).isoformat()
    v = (await ctx["req"].post(R, json={"visitor_name": "Kelmaydigan", "expected_at": exp})).json()
    v2 = (await ctx["req"].post(R, json={"visitor_name": "Bekor", "expected_at": exp})).json()
    assert (await ctx["other"].post(f"{R}/{v2['id']}/cancel")).status_code == 404
    assert (await ctx["req"].post(f"{R}/{v2['id']}/cancel")).json()["status"] == "cancelled"
    assert (await ctx["req"].put(f"{R}/{v2['id']}", json={"visitor_name": "Bekor", "expected_at": exp})).status_code == 409

    async with SessionLocal() as db:
        assert await reception.watch(db, NOW + timedelta(hours=2)) == 0
        assert await reception.watch(db, NOW + timedelta(hours=6)) == 1
        await db.commit()
    assert (await ctx["req"].get(f"{R}/{v['id']}")).json()["status"] == "no_show"

    lst = (await ctx["desk"].get(R, params={"scope": "all", "status": "open"})).json()
    assert [x["visitor_name"] for x in lst["items"]] == ["Kuryer Bobur"]
    s = (await ctx["desk"].get(R, params={"scope": "all", "q": "01B777"})).json()
    assert s["total"] == 1
    # direktor faqat o'qiydi
    d, _ = await as_user(new_client, "dir", "direktor")
    assert (await d.get(R, params={"scope": "all"})).json()["total"] == 3
    assert (await d.post(f"{R}/{lst['items'][0]['id']}/leave")).status_code == 403
