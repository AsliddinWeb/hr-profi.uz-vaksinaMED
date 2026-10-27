from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from app.db import SessionLocal
from app.models.tasks import Task
from app.services import tasks as svc
from app.timeutil import tz
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

T = "/api/v1/tasks"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=tz())


@pytest.fixture
def clock(monkeypatch):
    state = {"t": NOW}
    fn = lambda: state["t"]  # noqa: E731
    for mod in ("app.api.tasks", "app.services.tasks"):
        monkeypatch.setattr(f"{mod}.now", fn)
    return state


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def setup(new_client):
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    boss, boss_id = await as_user(new_client, "boss", "koordinator")
    a, a_id = await as_user(new_client, "ali", "farmasevt")
    b, b_id = await as_user(new_client, "bob", "farmasevt")
    return {"hr": hr, "hr_id": hr_id, "boss": boss, "boss_id": boss_id, "a": a, "a_id": a_id, "b": b, "b_id": b_id}


async def mk(c, title="Hisobot tayyorlash", **kw):
    r = await c.post(T, json={"title": title, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_assign_permissions_and_notifications(new_client, clock):
    ctx = await setup(new_client)
    own = await mk(ctx["a"], assignee_id=ctx["a_id"])
    assert own["status"] == "todo" and own["assignee"]["id"] == ctx["a_id"] and own["creator"]["id"] == ctx["a_id"]
    r = await ctx["a"].post(T, json={"title": "X", "assignee_id": ctx["b_id"]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "cannot_assign_others"

    t = await mk(ctx["boss"], "Inventarizatsiya", assignee_id=ctx["a_id"], watchers=[ctx["b_id"]], labels=["ombor", "Ombor", "tezkor"], priority="high")
    assert t["labels"] == ["ombor", "tezkor"]  # katta-kichik harf takrorlanmaydi
    assert "tasks.assigned" in [n["kind"] for n in (await ctx["a"].get("/api/v1/notifications")).json()["items"]]
    assert (await ctx["boss"].post(T, json={"title": "X", "assignee_id": 99999})).json()["detail"]["code"] == "unknown_user"
    assert (await ctx["boss"].post(T, json={"title": "X", "labels": list("abcdef")})).json()["detail"]["code"] == "too_many_labels"
    assert (await ctx["boss"].post(T, json={"title": ""})).status_code == 422
    assert (await ctx["a"].get(f"{T}/summary")).json() == {"open": 2, "overdue": 0}


async def test_visibility_and_scopes(new_client, clock):
    ctx = await setup(new_client)
    t = await mk(ctx["boss"], "Maxfiy reja", assignee_id=ctx["a_id"], watchers=[ctx["b_id"]])
    stranger, _ = await as_user(new_client, "eve", "farmasevt")
    assert (await stranger.get(f"{T}/{t['id']}")).status_code == 404
    assert (await stranger.get(T, params={"scope": "all"})).json()["total"] == 0
    for c in (ctx["a"], ctx["b"], ctx["hr"]):  # ijrochi, kuzatuvchi, hamma narsani ko'ruvchi
        assert (await c.get(f"{T}/{t['id']}")).status_code == 200
    assert (await ctx["b"].get(T, params={"scope": "watching"})).json()["total"] == 1
    assert (await ctx["b"].get(T, params={"scope": "mine"})).json()["total"] == 0
    assert (await ctx["boss"].get(T, params={"scope": "created"})).json()["total"] == 1
    assert (await ctx["a"].get(T, params={"scope": "all"})).json()["total"] == 1  # ko'rish huquqi bilan cheklangan
    assert (await ctx["hr"].get(T, params={"scope": "all"})).json()["total"] == 1
    assert (await stranger.get(f"{T}/analytics", params={"start": "2026-11-01", "end": "2026-11-30", "scope": "all"})).status_code == 403


async def test_status_rules(new_client, clock):
    ctx = await setup(new_client)
    t = await mk(ctx["boss"], assignee_id=ctx["a_id"])
    tid = t["id"]
    assert (await ctx["a"].post(f"{T}/{tid}/move", json={"status": "in_progress"})).json()["status"] == "in_progress"
    assert (await ctx["a"].post(f"{T}/{tid}/move", json={"status": "review"})).status_code == 200
    r = await ctx["a"].post(f"{T}/{tid}/move", json={"status": "done"})  # bajaruvchi yopa olmaydi
    assert r.status_code == 403
    assert (await ctx["b"].post(f"{T}/{tid}/move", json={"status": "done"})).status_code == 404
    clock["t"] = NOW + timedelta(hours=5)
    d = (await ctx["boss"].post(f"{T}/{tid}/move", json={"status": "done"})).json()
    assert d["status"] == "done" and d["completed_at"]
    assert (await ctx["a"].post(f"{T}/{tid}/move", json={"status": "in_progress"})).status_code == 403  # qayta ochish: yaratuvchi
    r = await ctx["boss"].post(f"{T}/{tid}/move", json={"status": "in_progress"})
    assert r.json()["completed_at"] is None
    n = [x["kind"] for x in (await ctx["a"].get("/api/v1/notifications")).json()["items"]]
    assert n.count("tasks.status") == 2  # yaratuvchi o'zgartirganda ijrochiga xabar

    # o'ziga o'zi bergan topshiriqni o'zi yopadi
    mine = await mk(ctx["a"], assignee_id=ctx["a_id"])
    assert (await ctx["a"].post(f"{T}/{mine['id']}/move", json={"status": "done"})).json()["status"] == "done"
    ev = (await ctx["a"].get(f"{T}/{tid}")).json()["events"]
    assert [e["action"] for e in ev] == ["created", "status", "status", "status", "status"]


async def test_board_order_and_done_window(new_client, clock):
    ctx = await setup(new_client)
    ids = [(await mk(ctx["a"], f"T{i}", assignee_id=ctx["a_id"]))["id"] for i in range(3)]
    board = (await ctx["a"].get(f"{T}/board")).json()
    assert [x["id"] for x in board["todo"]["tasks"]] == ids

    # oxirgisini birinchisidan oldinga qo'yamiz
    await ctx["a"].post(f"{T}/{ids[2]}/move", json={"status": "todo", "before_id": ids[0]})
    assert [x["id"] for x in (await ctx["a"].get(f"{T}/board")).json()["todo"]["tasks"]] == [ids[2], ids[0], ids[1]]
    # o'rtaga: 1-chi 0-dan oldin
    await ctx["a"].post(f"{T}/{ids[1]}/move", json={"status": "todo", "before_id": ids[0]})
    assert [x["id"] for x in (await ctx["a"].get(f"{T}/board")).json()["todo"]["tasks"]] == [ids[2], ids[1], ids[0]]

    # boshqa ustun: oxiriga
    await ctx["a"].post(f"{T}/{ids[0]}/move", json={"status": "in_progress"})
    await ctx["a"].post(f"{T}/{ids[1]}/move", json={"status": "in_progress", "before_id": ids[0]})
    b = (await ctx["a"].get(f"{T}/board")).json()
    assert [x["id"] for x in b["in_progress"]["tasks"]] == [ids[1], ids[0]] and b["todo"]["total"] == 1

    # bajarilganlar faqat oxirgi 14 kun
    await ctx["a"].post(f"{T}/{ids[2]}/move", json={"status": "done"})
    assert (await ctx["a"].get(f"{T}/board")).json()["done"]["total"] == 1
    async with SessionLocal() as s:
        await s.execute(update(Task).where(Task.id == ids[2]).values(completed_at=NOW - timedelta(days=30)))
        await s.commit()
    assert (await ctx["a"].get(f"{T}/board")).json()["done"]["total"] == 0
    assert (await ctx["a"].get(T, params={"status": "done"})).json()["total"] == 1  # ro'yxatda hamon bor


async def test_comments_chat(new_client, clock):
    ctx = await setup(new_client)
    t = await mk(ctx["boss"], assignee_id=ctx["a_id"], watchers=[ctx["b_id"]])
    tid = t["id"]
    c1 = (await ctx["a"].post(f"{T}/{tid}/comments", json={"body": "Boshladim"})).json()
    await ctx["boss"].post(f"{T}/{tid}/comments", json={"body": "Yaxshi, muddatga yetkazing"})
    allc = (await ctx["b"].get(f"{T}/{tid}/comments")).json()
    assert [c["body"] for c in allc] == ["Boshladim", "Yaxshi, muddatga yetkazing"] and allc[0]["author"]["name"] == "Ali"
    assert [c["body"] for c in (await ctx["a"].get(f"{T}/{tid}/comments", params={"after_id": c1["id"]})).json()] == ["Yaxshi, muddatga yetkazing"]
    kinds = lambda items: [n["kind"] for n in items]  # noqa: E731
    assert kinds((await ctx["boss"].get("/api/v1/notifications")).json()["items"]).count("tasks.comment") == 1  # o'z izohiga xabar yo'q
    assert kinds((await ctx["b"].get("/api/v1/notifications")).json()["items"]).count("tasks.comment") == 2
    stranger, _ = await as_user(new_client, "eve", "farmasevt")
    assert (await stranger.post(f"{T}/{tid}/comments", json={"body": "x"})).status_code == 404
    assert (await ctx["a"].post(f"{T}/{tid}/comments", json={"body": ""})).status_code == 422
    assert (await ctx["hr"].post(f"{T}/{tid}/comments", json={"body": "HR ko'rib chiqdi"})).status_code == 201  # tasks.manage

    await ctx["boss"].delete(f"{T}/{tid}")
    assert (await ctx["a"].post(f"{T}/{tid}/comments", json={"body": "kech"})).status_code in (403, 404)


async def test_files(new_client, clock):
    ctx = await setup(new_client)
    tid = (await mk(ctx["boss"], assignee_id=ctx["a_id"], watchers=[ctx["b_id"]]))["id"]
    pdf = b"%PDF-1.4 hisobot"
    r = await ctx["a"].post(f"{T}/{tid}/files", files={"file": ("hisobot.pdf", pdf, "application/pdf")})
    assert r.status_code == 201 and r.json()["filename"] == "hisobot.pdf" and r.json()["size"] == len(pdf)
    fid = r.json()["id"]
    assert (await ctx["a"].post(f"{T}/{tid}/files", files={"file": ("virus.exe", b"MZ\x90", "application/octet-stream")})).status_code == 415
    got = await ctx["b"].get(f"{T}/{tid}/files/{fid}")
    assert got.status_code == 200 and got.content == pdf and "attachment" in got.headers["content-disposition"]
    assert (await ctx["a"].get(f"{T}/{tid}")).json()["files"] == 1
    assert (await ctx["b"].delete(f"{T}/{tid}/files/{fid}")).status_code == 403  # yuklagan ham, yaratuvchi ham emas
    assert (await ctx["boss"].delete(f"{T}/{tid}/files/{fid}")).status_code == 204
    assert (await ctx["a"].get(f"{T}/{tid}/files/{fid}")).status_code == 404
    ev = [e["action"] for e in (await ctx["a"].get(f"{T}/{tid}")).json()["events"]]
    assert ev == ["created", "file_added", "file_removed"]


async def test_update_history_and_edit_rights(new_client, clock):
    ctx = await setup(new_client)
    t = await mk(ctx["boss"], "Eski nom", assignee_id=ctx["a_id"], due_at="2026-11-12T10:00:00+05:00")
    tid = t["id"]
    body = {"title": "Yangi nom", "priority": "urgent", "assignee_id": ctx["b_id"], "due_at": "2026-11-14T10:00:00+05:00", "description": "Tafsilot"}
    assert (await ctx["a"].put(f"{T}/{tid}", json=body)).status_code == 403  # ijrochi tahrirlay olmaydi
    r = await ctx["boss"].put(f"{T}/{tid}", json=body)
    assert r.status_code == 200 and r.json()["title"] == "Yangi nom" and r.json()["assignee"]["id"] == ctx["b_id"]
    ev = (await ctx["boss"].get(f"{T}/{tid}")).json()["events"][-1]
    assert ev["action"] == "updated" and set(ev["data"]) == {"title", "priority", "assignee_id", "due_at", "description"}
    assert "tasks.assigned" in [n["kind"] for n in (await ctx["b"].get("/api/v1/notifications")).json()["items"]]
    assert (await ctx["hr"].put(f"{T}/{tid}", json={**body, "title": "HR tahriri"})).json()["title"] == "HR tahriri"  # tasks.manage
    assert (await ctx["boss"].put(f"{T}/{tid}", json=body | {"watchers": list(range(100, 112))})).json()["detail"]["code"] == "too_many_watchers"
    assert (await ctx["b"].delete(f"{T}/{tid}")).status_code == 403
    assert (await ctx["boss"].delete(f"{T}/{tid}")).status_code == 204
    assert (await ctx["boss"].get(T, params={"scope": "created"})).json()["total"] == 0  # arxivlangan ko'rinmaydi


async def test_deadline_notifications(new_client, clock):
    ctx = await setup(new_client)
    soon = await mk(ctx["boss"], "Yaqin", assignee_id=ctx["a_id"], due_at=(NOW + timedelta(hours=23)).isoformat())
    far = await mk(ctx["boss"], "Uzoq", assignee_id=ctx["a_id"], due_at=(NOW + timedelta(hours=30)).isoformat())
    late = await mk(ctx["boss"], "Kech", assignee_id=ctx["a_id"], due_at=(NOW - timedelta(hours=2)).isoformat())
    done = await mk(ctx["boss"], "Tayyor", assignee_id=ctx["a_id"], due_at=(NOW - timedelta(hours=2)).isoformat())
    await ctx["boss"].post(f"{T}/{done['id']}/move", json={"status": "done"})

    async def run(at):
        async with SessionLocal() as s:
            n_soon, n_late, notes = await svc.check_deadlines(s, at)
            await s.commit()
            return n_soon, n_late, notes

    n_soon, n_late, notes = await run(NOW)
    assert (n_soon, n_late) == (1, 1)  # "Uzoq" 24 soatdan keyin, "Tayyor" bajarilgan
    assert sorted(n.kind for n in notes) == ["tasks.due_soon", "tasks.overdue", "tasks.overdue"]  # kech: ijrochi + yaratuvchi
    assert (await run(NOW))[:2] == (0, 0)  # takrorlanmaydi
    assert (await run(NOW + timedelta(hours=25)))[:2] == (1, 1)  # "Uzoq" endi yaqin, "Yaqin" muddati o'tdi
    assert (await ctx["a"].get(f"{T}/summary")).json()["overdue"] == 1
    ev = [e["action"] for e in (await ctx["boss"].get(f"{T}/{late['id']}")).json()["events"]]
    assert "overdue" in ev
    assert far and soon

    # muddat o'zgarsa qayta ogohlantiriladi
    await ctx["boss"].put(f"{T}/{late['id']}", json={"title": "Kech", "assignee_id": ctx["a_id"], "due_at": (NOW + timedelta(hours=40)).isoformat()})
    async with SessionLocal() as s:
        assert (await s.get(Task, late["id"])).notified_overdue is False


async def test_templates(new_client, clock):
    ctx = await setup(new_client)
    body = {"name": "Haftalik hisobot", "title": "Haftalik hisobotni topshirish", "priority": "high", "due_days": 3, "labels": ["hisobot"], "description": "Shablon bo'yicha"}
    assert (await ctx["a"].post(f"{T}/templates", json=body)).status_code == 403
    t = (await ctx["hr"].post(f"{T}/templates", json=body)).json()
    assert (await ctx["hr"].post(f"{T}/templates", json={**body, "name": "haftalik HISOBOT"})).json()["detail"]["code"] == "template_name_taken"
    await ctx["hr"].post(f"{T}/templates", json={**body, "name": "Nofaol", "is_active": False})
    assert [x["name"] for x in (await ctx["a"].get(f"{T}/templates")).json()] == ["Haftalik hisobot"]  # oddiy foydalanuvchi faqat faollarini
    assert len((await ctx["hr"].get(f"{T}/templates")).json()) == 2
    assert (await ctx["a"].get(f"{T}/templates/{t['id']}")).json()["due_days"] == 3
    assert (await ctx["hr"].put(f"{T}/templates/{t['id']}", json={**body, "title": "Yangi sarlavha"})).json()["title"] == "Yangi sarlavha"
    assert (await ctx["hr"].delete(f"{T}/templates/{t['id']}")).status_code == 204
    # shablondan yaratilgan topshiriq o'zi saqlanadi
    task = await mk(ctx["a"], "Shablondan", template_id=None)
    assert task["id"]


async def test_analytics_calendar_and_summary(new_client, clock):
    ctx = await setup(new_client)
    due = lambda h: (NOW + timedelta(hours=h)).isoformat()  # noqa: E731
    a1 = await mk(ctx["boss"], "Vaqtida", assignee_id=ctx["a_id"], due_at=due(24))
    a2 = await mk(ctx["boss"], "Kech tugadi", assignee_id=ctx["a_id"], due_at=due(2), priority="urgent")
    a3 = await mk(ctx["boss"], "Ochiq o'tgan", assignee_id=ctx["a_id"], due_at=due(-5))
    b1 = await mk(ctx["boss"], "Boshqa ijrochi", assignee_id=ctx["b_id"], due_at=due(48))

    clock["t"] = NOW + timedelta(hours=10)  # a1 vaqtida (muddatdan 14 soat oldin), a2 kech (8 soat o'tib)
    await ctx["boss"].post(f"{T}/{a1['id']}/move", json={"status": "done"})
    await ctx["boss"].post(f"{T}/{a2['id']}/move", json={"status": "done"})
    clock["t"] = NOW + timedelta(hours=12)

    q = {"start": "2026-11-10", "end": "2026-11-11"}
    r = (await ctx["hr"].get(f"{T}/analytics", params={**q, "scope": "all"})).json()
    k = r["kpis"]
    assert (k["created"], k["completed"], k["open"], k["overdue"]) == (4, 2, 2, 1)
    assert k["on_time_rate"] == 0.5 and k["avg_hours"] == 10.0
    assert r["by_status"] == {"todo": 2, "in_progress": 0, "review": 0, "done": 2}
    assert r["by_priority"]["urgent"] == 0 and r["by_priority"]["normal"] == 2
    ali = next(x for x in r["by_assignee"] if x["user"]["name"] == "Ali")
    assert (ali["assigned"], ali["done"], ali["open"], ali["overdue"]) == (3, 2, 1, 1) and ali["avg_hours"] == 10.0
    assert r["by_assignee"][0]["user"]["name"] == "Ali"  # eng ko'p kechikkan tepada
    assert sum(d["created"] for d in r["trend"]) == 4 and sum(d["completed"] for d in r["trend"]) == 2
    assert [d["date"] for d in r["trend"]] == ["2026-11-10", "2026-11-11"]
    mine = (await ctx["b"].get(f"{T}/analytics", params=q)).json()["kpis"]  # o'zimniki
    assert mine["created"] == 1 and mine["open"] == 1
    assert (await ctx["hr"].get(f"{T}/analytics", params={"start": "2026-01-01", "end": "2026-12-31"})).status_code == 400

    cal = (await ctx["a"].get(f"{T}/calendar", params={"month": "2026-11", "scope": "mine"})).json()["items"]
    assert [i["title"] for i in cal] == ["Ochiq o'tgan", "Kech tugadi", "Vaqtida"]
    assert (await ctx["a"].get(f"{T}/calendar", params={"month": "2026-12"})).json()["items"] == []
    assert a3 and b1
    assert (await ctx["a"].get(T, params={"overdue": "true"})).json()["total"] == 1
    assert (await ctx["a"].get(T, params={"sort": "priority", "status": "open"})).json()["items"][0]["title"] in ("Ochiq o'tgan",)
    assert (await ctx["a"].get(f"{T}/assignees", params={"q": "bo"})).json()[0]["name"] in ("Bob", "Boss")
