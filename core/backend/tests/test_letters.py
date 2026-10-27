from datetime import date

import pytest
from sqlalchemy import update

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.letters import ExplanationLetter
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

L = "/api/v1/letters"
PW = "Passw0rd-test"


async def as_user(new_client, login_name, role):
    uid = await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def setup(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    coord, coord_id = await as_user(new_client, "coord", "koordinator")
    emp, emp_uid = await as_user(new_client, "ali", "farmasevt")
    other, other_uid = await as_user(new_client, "bob", "farmasevt")
    branch = (await hr.post("/api/v1/branches", json={"number": 3, "name": "F3", "coordinator_user_id": coord_id})).json()
    other_branch = (await hr.post("/api/v1/branches", json={"number": 4, "name": "F4"})).json()
    async with SessionLocal() as s:
        e = Employee(last_name="Aliyev", first_name="Ali", full_name="Aliyev Ali", user_id=emp_uid, branch_id=branch["id"], status="active")
        o = Employee(last_name="Bekov", first_name="Bek", full_name="Bekov Bek", user_id=other_uid, branch_id=other_branch["id"], status="active")
        s.add_all([e, o])
        await s.commit()
        ids = (e.id, o.id)
    return {"hr": hr, "coord": coord, "emp": emp, "other": other, "emp_id": ids[0], "other_id": ids[1]}


def issue_body(emp_id, **kw):
    return {"employee_id": emp_id, "incident_type": "late", "incident_date": "2026-10-20", "incident_note": "20-oktabrda 40 daqiqa kechikdingiz", **kw}


async def issue(c, emp_id, **kw):
    r = await c.post(L, json=issue_body(emp_id, **kw))
    assert r.status_code == 201, r.text
    return r.json()


async def sign(c, lid, text="Transport tiqilinchi sababli kechikdim, ogohlantirishga ulgurmadim.", password=PW):
    return await c.post(f"{L}/{lid}/submit", json={"explanation": text, "password": password})


async def test_issue_scopes_and_validation(new_client):
    ctx = await setup(new_client)
    letter = await issue(ctx["hr"], ctx["emp_id"])
    assert letter["status"] == "requested" and letter["number"].startswith("TX-") and letter["due_date"]

    # koordinator faqat o'z filiali xodimiga; xodim hech kimga so'ray olmaydi
    assert (await ctx["coord"].post(L, json=issue_body(ctx["emp_id"]))).status_code == 201
    assert (await ctx["coord"].post(L, json=issue_body(ctx["other_id"]))).status_code == 403
    assert (await ctx["emp"].post(L, json=issue_body(ctx["other_id"]))).status_code == 403
    assert (await ctx["hr"].post(L, json=issue_body(ctx["emp_id"], incident_date="2030-01-01"))).json()["detail"]["code"] == "date_in_future"
    assert (await ctx["hr"].post(L, json=issue_body(ctx["emp_id"], template_id=999))).json()["detail"]["code"] == "unknown_template"

    notes = (await ctx["emp"].get("/api/v1/notifications")).json()["items"]
    assert all(n["kind"] == "letters.requested" for n in notes) and any(letter["number"] in n["body"]["uz"] for n in notes)
    assert (await ctx["emp"].get(f"{L}/summary")).json() == {"to_write": 2, "to_review": 0}


async def test_submit_with_password_signature_and_snapshot(new_client):
    ctx = await setup(new_client)
    lid = (await issue(ctx["hr"], ctx["emp_id"]))["id"]

    assert (await ctx["hr"].post(f"{L}/{lid}/submit", json={"explanation": "x" * 20, "password": PW})).status_code == 403  # xodim emas
    assert (await sign(ctx["emp"], lid, text="qisqa")).json()["detail"]["code"] == "explanation_short"
    r = await sign(ctx["emp"], lid, password="wrong")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "wrong_password"

    r = await sign(ctx["emp"], lid)
    assert r.status_code == 200 and r.json()["status"] == "submitted" and r.json()["signed"]
    d = (await ctx["emp"].get(f"{L}/{lid}")).json()
    assert "Aliyev Ali" in d["snapshot"]["body"] and "Transport tiqilinchi" in d["snapshot"]["body"] and "20.10.2026" in d["snapshot"]["body"]
    assert d["signature"]["name"] == "Ali" and len(d["content_hash"]) == 64
    assert [e["action"] for e in d["events"]] == ["requested", "submitted"]
    assert (await sign(ctx["emp"], lid)).json()["detail"]["code"] == "letter_not_open"

    # HR ga xabar, ko'rib chiqish navbatida
    assert (await ctx["hr"].get(f"{L}/summary")).json()["to_review"] == 1
    assert "letters.submitted" in [n["kind"] for n in (await ctx["hr"].get("/api/v1/notifications")).json()["items"]]
    assert (await ctx["hr"].get("/api/v1/audit", params={"action": "letters.submit"})).json()["total"] == 1


async def test_password_lockout(new_client):
    ctx = await setup(new_client)
    lid = (await issue(ctx["hr"], ctx["emp_id"]))["id"]
    for _ in range(5):
        assert (await sign(ctx["emp"], lid, password="bad")).json()["detail"]["code"] == "wrong_password"
    r = await sign(ctx["emp"], lid)  # to'g'ri parol ham bloklangan
    assert r.status_code == 429


async def test_review_return_resubmit_accept(new_client):
    ctx = await setup(new_client)
    lid = (await issue(ctx["coord"], ctx["emp_id"]))["id"]  # koordinator so'radi
    await sign(ctx["emp"], lid)
    first_hash = (await ctx["emp"].get(f"{L}/{lid}")).json()["content_hash"]

    assert (await ctx["emp"].post(f"{L}/{lid}/review", json={"action": "accept"})).status_code == 403  # o'z xatini
    assert (await ctx["hr"].post(f"{L}/{lid}/review", json={"action": "return"})).json()["detail"]["code"] == "note_required"
    r = await ctx["coord"].post(f"{L}/{lid}/review", json={"action": "return", "note": "Sababni aniqroq yozing"})  # so'ragan koordinator ham ko'ra oladi
    assert r.status_code == 200 and r.json()["status"] == "returned"
    n = (await ctx["emp"].get("/api/v1/notifications")).json()["items"][0]
    assert n["kind"] == "letters.returned" and "Sababni aniqroq" in n["body"]["uz"]

    assert (await sign(ctx["emp"], lid, text="Avtobus buzilib qoldi, ish haqida dispetcherga qo'ng'iroq qildim.")).status_code == 200
    d = (await ctx["emp"].get(f"{L}/{lid}")).json()
    assert d["content_hash"] != first_hash and d["review_note"] is None
    assert (await ctx["hr"].post(f"{L}/{lid}/review", json={"action": "accept"})).json()["status"] == "accepted"
    assert (await ctx["hr"].post(f"{L}/{lid}/review", json={"action": "accept"})).json()["detail"]["code"] == "letter_not_submitted"
    assert "letters.accepted" in [n["kind"] for n in (await ctx["emp"].get("/api/v1/notifications")).json()["items"]]


async def test_pdf_and_public_verification(new_client):
    ctx = await setup(new_client)
    lid = (await issue(ctx["hr"], ctx["emp_id"]))["id"]
    assert (await ctx["emp"].get(f"{L}/{lid}/pdf")).status_code == 409  # hali imzolanmagan
    await sign(ctx["emp"], lid)

    r = await ctx["emp"].get(f"{L}/{lid}/pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF" and len(r.content) > 2000

    detail = (await ctx["hr"].get(f"{L}/{lid}")).json()
    anon = new_client()  # kirmagan
    v = await anon.get(f"/api/v1/public/letters/{detail['code']}")
    assert v.status_code == 200, v.text
    body = v.json()
    assert body["valid"] and body["intact"] and body["number"] == detail["number"] and body["status"] == "submitted"
    assert body["employee"] == "Aliyev A."  # to'liq ism va matn oshkor etilmaydi
    assert "Transport" not in v.text and "explanation" not in body

    assert (await anon.get(f"/api/v1/public/letters/{detail['code']}", params={"hash": detail["content_hash"][:12]})).json()["hash_match"] is True
    assert (await anon.get(f"/api/v1/public/letters/{detail['code']}", params={"hash": "deadbeef"})).json()["hash_match"] is False
    assert (await anon.get("/api/v1/public/letters/nope")).status_code == 404

    # bazadagi matn o'zgartirilsa yaxlitlik buziladi
    async with SessionLocal() as s:
        await s.execute(update(ExplanationLetter).where(ExplanationLetter.id == lid).values(explanation="Soxta matn kiritildi, boshqacha."))
        await s.commit()
    assert (await anon.get(f"/api/v1/public/letters/{detail['code']}")).json()["intact"] is False


async def test_scan_upload_and_download(new_client):
    ctx = await setup(new_client)
    lid = (await issue(ctx["hr"], ctx["emp_id"]))["id"]
    pdf = b"%PDF-1.4 scan content"
    files = {"file": ("scan.pdf", pdf, "application/pdf")}
    assert (await ctx["emp"].post(f"{L}/{lid}/scan", files=files)).status_code == 403  # hali topshirilmagan
    await sign(ctx["emp"], lid)
    assert (await ctx["emp"].post(f"{L}/{lid}/scan", files={"file": ("x.exe", b"MZ\x90\x00", "application/octet-stream")})).status_code == 415
    assert (await ctx["emp"].post(f"{L}/{lid}/scan", files=files)).status_code == 204
    assert (await ctx["other"].post(f"{L}/{lid}/scan", files=files)).status_code == 404
    r = await ctx["hr"].get(f"{L}/{lid}/scan")
    assert r.status_code == 200 and r.content == pdf and r.headers["content-type"] == "application/pdf"
    assert (await ctx["hr"].get(f"{L}/{lid}")).json()["has_scan"] is True
    assert (await ctx["other"].get(f"{L}/{lid}/scan")).status_code == 404


async def test_cancel_and_visibility(new_client):
    ctx = await setup(new_client)
    a = (await issue(ctx["hr"], ctx["emp_id"]))["id"]
    b = (await issue(ctx["coord"], ctx["emp_id"]))["id"]
    assert (await ctx["other"].get(f"{L}/{a}")).status_code == 404
    assert (await ctx["other"].get(L, params={"scope": "all"})).status_code == 403
    assert (await ctx["hr"].get(L, params={"scope": "all"})).json()["total"] == 2
    assert (await ctx["coord"].get(L, params={"scope": "issued"})).json()["total"] == 1
    assert (await ctx["emp"].post(f"{L}/{a}/cancel")).status_code == 403
    assert (await ctx["coord"].post(f"{L}/{a}/cancel")).status_code in (403, 404)  # boshqa so'ragan xat
    assert (await ctx["coord"].post(f"{L}/{b}/cancel")).json()["status"] == "cancelled"
    assert (await ctx["hr"].post(f"{L}/{a}/cancel")).json()["status"] == "cancelled"
    assert (await ctx["hr"].post(f"{L}/{a}/cancel")).json()["detail"]["code"] == "cannot_cancel"
    assert (await sign(ctx["emp"], a)).json()["detail"]["code"] == "letter_not_open"


async def test_overdue_filter(new_client):
    ctx = await setup(new_client)
    lid = (await issue(ctx["hr"], ctx["emp_id"], due_date="2026-12-31"))["id"]
    async with SessionLocal() as s:
        await s.execute(update(ExplanationLetter).where(ExplanationLetter.id == lid).values(due_date=date(2020, 1, 1)))
        await s.commit()
    r = (await ctx["emp"].get(L, params={"scope": "mine", "status": "overdue"})).json()
    assert r["total"] == 1 and r["items"][0]["overdue"] is True


async def test_template_management(new_client):
    ctx = await setup(new_client)
    hr = ctx["hr"]
    base = {"name": "Qisqa", "title": "XAT", "recipient_line": "{company}ga", "body_template": "Men {employee_name}: {explanation}"}
    assert (await ctx["emp"].get(f"{L}/templates")).status_code == 403
    assert (await ctx["emp"].post(f"{L}/templates", json=base)).status_code == 403
    r = await hr.post(f"{L}/templates", json={**base, "body_template": "Men {employee_name}: {hack.x} {explanation}"})
    assert r.json()["detail"]["code"] == "unknown_placeholder" and r.json()["detail"]["names"] == ["hack.x"]
    assert (await hr.post(f"{L}/templates", json={**base, "body_template": "Matnda tushuntirish joyi yo'q."})).json()["detail"]["code"] == "explanation_placeholder_missing"
    t = (await hr.post(f"{L}/templates", json=base)).json()
    assert (await hr.post(f"{L}/templates", json={**base, "name": "qisqa"})).json()["detail"]["code"] == "template_name_taken"

    # yangi standart; eskisi standartligini yo'qotadi, standartni o'chirib bo'lmaydi
    await hr.put(f"{L}/templates/{t['id']}", json={**base, "is_default": True})
    tpls = {x["name"]: x for x in (await hr.get(f"{L}/templates")).json()}
    assert tpls["Qisqa"]["is_default"] and not tpls["Standart tushuntirish xati"]["is_default"]
    assert (await hr.delete(f"{L}/templates/{t['id']}")).json()["detail"]["code"] == "default_template_required"

    # shablon xatda ishlatilsa o'chirib bo'lmaydi, imzolangan matn muhrlangan qoladi
    lid = (await issue(hr, ctx["emp_id"]))["id"]
    await sign(ctx["emp"], lid, text="Matn yetarlicha uzun bo'lishi kerak edi.")
    await hr.put(f"{L}/templates/{t['id']}", json={**base, "title": "BOSHQA SARLAVHA", "is_default": True})
    assert (await hr.get(f"{L}/{lid}")).json()["snapshot"]["title"] == "XAT"
    old = tpls["Standart tushuntirish xati"]
    assert (await hr.delete(f"{L}/templates/{old['id']}")).status_code == 204
    assert (await hr.delete(f"{L}/templates/{t['id']}")).status_code == 409
