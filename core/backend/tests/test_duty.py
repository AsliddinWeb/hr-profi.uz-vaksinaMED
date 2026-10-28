from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.duty import DutyRun
from app.models.employees import Employee
from app.services import duty as svc
from app.timeutil import now
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

D = "/api/v1/duty"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


def items():
    return [{"text": "Kassa tozalandi", "kind": "yesno"}, {"text": "Javon tartibi", "kind": "score"}, {"text": "Izoh (ixtiyoriy)", "kind": "yesno", "required": False}]


async def setup(new_client):
    hr, _ = await as_user(new_client, "hrm", "hr_menejer")
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    aud, _ = await as_user(new_client, "auditor", "hr_auditor")
    mudir, mudir_id = await as_user(new_client, "mudir", "mudir")
    stranger, _ = await as_user(new_client, "mudir2", "mudir")
    far, far_uid = await as_user(new_client, "far", "farmasevt")
    plain, plain_uid = await as_user(new_client, "plain", "farmasevt")
    dept = (await hrd.post("/api/v1/org/departments", json={"name": "Dorixona"})).json()
    pos = (await hrd.post("/api/v1/org/positions", json={"name": "Farmasevt", "department_id": dept["id"]})).json()
    other_pos = (await hrd.post("/api/v1/org/positions", json={"name": "Mudir lav", "department_id": dept["id"]})).json()
    branch = (await hrd.post("/api/v1/branches", json={"number": 81, "name": "F81", "manager_user_id": mudir_id})).json()
    async with SessionLocal() as s:
        e = Employee(last_name="Far", first_name="X", full_name="Far X", user_id=far_uid, status="active", branch_id=branch["id"], department_id=dept["id"], position_id=pos["id"], hire_date=date(2026, 1, 1))
        e2 = Employee(last_name="Plain", first_name="Y", full_name="Plain Y", user_id=plain_uid, status="active", branch_id=branch["id"], department_id=dept["id"], position_id=other_pos["id"], hire_date=date(2026, 1, 1))
        s.add_all([e, e2])
        await s.commit()
        emp, emp2 = e.id, e2.id
    return {"hr": hr, "aud": aud, "mudir": mudir, "stranger": stranger, "far": far, "plain": plain, "dept": dept["id"], "pos": pos["id"], "other_pos": other_pos["id"], "emp": emp, "emp2": emp2, "branch": branch["id"]}


def tpl(**kw):
    return {"name": "Kunlik", "scope": "position", "frequency": "daily", "deadline_time": "20:00", "items": items(), **kw}


async def test_template_crud_and_access(new_client):
    ctx = await setup(new_client)
    assert (await ctx["far"].post(f"{D}/templates", json=tpl(position_id=ctx["pos"]))).status_code == 403
    assert (await ctx["mudir"].post(f"{D}/templates", json=tpl(position_id=ctx["pos"]))).status_code == 403
    assert (await ctx["hr"].post(f"{D}/templates", json=tpl())).json()["detail"]["code"] == "unknown_position"
    assert (await ctx["hr"].post(f"{D}/templates", json=tpl(scope="department"))).json()["detail"]["code"] == "unknown_department"
    r = await ctx["hr"].post(f"{D}/templates", json=tpl(position_id=ctx["pos"]))
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["position"] == "Farmasevt" and j["item_count"] == 3 and all(i["id"] for i in j["items"]) and j["deadline_time"] == "20:00"
    d = await ctx["hr"].post(f"{D}/templates", json=tpl(name="Bo'lim", scope="department", department_id=ctx["dept"], frequency="weekly"))
    assert d.status_code == 201 and d.json()["department"] == "Dorixona"
    # bo'lim filtri: bo'lim chek-listi + uning lavozimlariniki
    assert len((await ctx["hr"].get(f"{D}/templates", params={"department_id": ctx["dept"]})).json()) == 2
    assert len((await ctx["hr"].get(f"{D}/templates", params={"position_id": ctx["pos"]})).json()) == 1
    assert len((await ctx["aud"].get(f"{D}/templates")).json()) == 2  # auditor ko'radi
    assert (await ctx["aud"].put(f"{D}/templates/{j['id']}", json=tpl(position_id=ctx["pos"]))).status_code == 403
    u = await ctx["hr"].put(f"{D}/templates/{j['id']}", json=tpl(position_id=ctx["pos"], name="Yangi nom", items=items()[:1]))
    assert u.json()["name"] == "Yangi nom" and u.json()["item_count"] == 1
    assert (await ctx["hr"].post(f"{D}/templates", json=tpl(position_id=ctx["pos"], items=[{"text": " ", "kind": "yesno"}]))).status_code in (400, 422)
    assert (await ctx["hr"].delete(f"{D}/templates/{d.json()['id']}")).status_code == 204


async def test_my_checklist_flow_and_scoring(new_client):
    ctx = await setup(new_client)
    pos_tpl = (await ctx["hr"].post(f"{D}/templates", json=tpl(position_id=ctx["pos"]))).json()
    await ctx["hr"].post(f"{D}/templates", json=tpl(name="Bo'lim", scope="department", department_id=ctx["dept"]))
    mine = (await ctx["far"].get(f"{D}/my")).json()
    assert {i["checklist"]["name"] for i in mine["items"]} == {"Kunlik", "Bo'lim"}  # lavozim + bo'lim
    assert all(i["status"] in ("open", "overdue") and i["run"] is None for i in mine["items"])
    other = (await ctx["plain"].get(f"{D}/my")).json()  # boshqa lavozim: faqat bo'lim chek-listi
    assert {i["checklist"]["name"] for i in other["items"]} == {"Bo'lim"}
    ids = [i["id"] for i in pos_tpl["items"]]
    # majburiy punkt javobsiz / noto'g'ri qiymat
    assert (await ctx["far"].put(f"{D}/my/{pos_tpl['id']}", json={"answers": {ids[0]: True}})).json()["detail"]["code"] == "answers_incomplete"
    assert (await ctx["far"].put(f"{D}/my/{pos_tpl['id']}", json={"answers": {ids[0]: "ha", ids[1]: 4}})).json()["detail"]["code"] == "answer_invalid"
    assert (await ctx["far"].put(f"{D}/my/{pos_tpl['id']}", json={"answers": {ids[0]: True, ids[1]: 9}})).json()["detail"]["code"] == "answer_invalid"
    ok = await ctx["far"].put(f"{D}/my/{pos_tpl['id']}", json={"answers": {ids[0]: True, ids[1]: 4}, "note": "Hammasi joyida"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["score_pct"] == 90  # (1 + 0.8) / 2
    again = (await ctx["far"].get(f"{D}/my")).json()
    done = next(i for i in again["items"] if i["checklist"]["id"] == pos_tpl["id"])
    assert done["status"] == "done" and done["run"]["note"] == "Hammasi joyida"
    # boshqa lavozim xodimi bu chek-listni to'ldira olmaydi
    assert (await ctx["plain"].put(f"{D}/my/{pos_tpl['id']}", json={"answers": {ids[0]: True, ids[1]: 4}})).status_code == 404
    # natijasi bor shablonni o'chirib bo'lmaydi
    assert (await ctx["hr"].delete(f"{D}/templates/{pos_tpl['id']}")).json()["detail"]["code"] == "in_use"


async def test_control_scope_and_statuses(new_client):
    ctx = await setup(new_client)
    t1 = (await ctx["hr"].post(f"{D}/templates", json=tpl(position_id=ctx["pos"]))).json()
    ids = [i["id"] for i in t1["items"]]
    await ctx["far"].put(f"{D}/my/{t1['id']}", json={"answers": {ids[0]: True, ids[1]: 5}})
    c = (await ctx["hr"].get(f"{D}/control")).json()
    assert c["kpis"]["expected"] == 1 and c["kpis"]["done"] == 1 and c["kpis"]["rate"] == 100
    assert c["rows"][0]["status"] == "done" and c["rows"][0]["score_pct"] == 100 and c["by_department"][0]["name"] == "Dorixona"
    # mudir o'z filialini ko'radi, begona mudir ko'ra olmaydi (403: filiali yo'q)
    assert (await ctx["mudir"].get(f"{D}/control")).json()["kpis"]["expected"] == 1
    assert (await ctx["stranger"].get(f"{D}/control")).status_code == 403
    assert (await ctx["far"].get(f"{D}/control")).status_code == 403
    # kelajak sanasida hammasi kutilmoqda
    future = (date.today() + timedelta(days=3)).isoformat()
    fc = (await ctx["hr"].get(f"{D}/control", params={"date": future, "status": "open"})).json()
    assert fc["kpis"]["open"] == 1 and fc["total"] == 1


async def test_overdue_scan_notifies_once(new_client):
    ctx = await setup(new_client)
    t1 = (await ctx["hr"].post(f"{D}/templates", json=tpl(position_id=ctx["pos"], deadline_time="00:00"))).json()  # muddat bugun 00:00: allaqachon o'tgan
    assert t1["id"]
    moment = now()
    async with SessionLocal() as s:
        n1 = await svc.overdue_scan(s, moment)
        await s.commit()
    assert len(n1) >= 2  # xodimga + mudirga
    far_notes = await notes(ctx["far"])
    assert any(n["kind"] == "duty.overdue" for n in far_notes)
    lead = await notes(ctx["mudir"])
    assert any(n["kind"] == "duty.overdue_lead" and "Far X" in n["body"]["uz"] for n in lead)
    async with SessionLocal() as s:
        assert await svc.overdue_scan(s, moment) == []  # ikkinchi marta yuborilmaydi
        runs = (await s.scalars(select(DutyRun))).all()
        assert len(runs) == 1 and runs[0].late_notified_at and runs[0].completed_at is None
    # bajargach kechikkan deb belgilanadi
    ids = [i["id"] for i in t1["items"]]
    r = await ctx["far"].put(f"{D}/my/{t1['id']}", json={"answers": {ids[0]: True, ids[1]: 3}})
    assert r.json()["run"]["late"] is True
    c = (await ctx["hr"].get(f"{D}/control")).json()
    assert c["rows"][0]["status"] == "done" and c["rows"][0]["late"] is True
