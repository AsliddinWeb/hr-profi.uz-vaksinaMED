from datetime import date

import pytest

from app.db import SessionLocal
from app.models.employees import Employee
from tests.conftest import PASSWORD, login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

S = "/api/v1/staffdocs"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def notes(c):
    return (await c.get("/api/v1/notifications")).json()["items"]


async def setup(new_client):
    hrd, _ = await as_user(new_client, "hrd", "hr_direktor")
    hrm, _ = await as_user(new_client, "hrm", "hr_menejer")
    aud, _ = await as_user(new_client, "auditor", "hr_auditor")
    far, far_uid = await as_user(new_client, "far", "farmasevt")
    other, other_uid = await as_user(new_client, "other", "farmasevt")
    async with SessionLocal() as s:
        e = Employee(last_name="Far", first_name="X", full_name="Far X", user_id=far_uid, status="active", hire_date=date(2026, 1, 1))
        e2 = Employee(last_name="Other", first_name="Y", full_name="Other Y", user_id=other_uid, status="active", hire_date=date(2026, 1, 1))
        s.add_all([e, e2])
        await s.commit()
        emp, emp2 = e.id, e2.id
    return {"hrd": hrd, "hrm": hrm, "aud": aud, "far": far, "other": other, "emp": emp, "emp2": emp2}


async def test_application_flow(new_client):
    ctx = await setup(new_client)
    bad = await ctx["far"].post(f"{S}/applications", json={"subtype": "vacation", "body": "Ta'til so'rayman"})
    assert bad.json()["detail"]["code"] == "dates_required"
    r = await ctx["far"].post(f"{S}/applications", json={"subtype": "vacation", "body": "Ta'til so'rayman", "start_date": "2026-12-01", "end_date": "2026-12-14"})
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["number"].startswith("AR-") and j["status"] == "submitted" and j["can"]["cancel"] and not j["can"]["decide"]
    assert any(n["kind"] == "staff.application_new" for n in await notes(ctx["hrm"]))
    # boshqa xodim ko'rmaydi, HR ko'radi
    assert (await ctx["other"].get(f"{S}/{j['id']}")).status_code == 404
    assert (await ctx["aud"].get(f"{S}/{j['id']}")).status_code == 200
    assert (await ctx["far"].post(f"{S}/{j['id']}/decide", json={"action": "approve"})).status_code == 403
    assert (await ctx["aud"].post(f"{S}/{j['id']}/decide", json={"action": "approve"})).status_code == 403  # auditor faqat o'qiydi
    assert (await ctx["hrm"].post(f"{S}/{j['id']}/decide", json={"action": "reject"})).json()["detail"]["code"] == "note_required"
    d = await ctx["hrm"].post(f"{S}/{j['id']}/decide", json={"action": "approve", "note": "Mayli"})
    assert d.json()["status"] == "approved" and d.json()["can"]["make_order"]
    assert any(n["kind"] == "staff.application_decided" for n in await notes(ctx["far"]))
    assert (await ctx["hrm"].post(f"{S}/{j['id']}/decide", json={"action": "reject", "note": "x"})).json()["detail"]["code"] == "already_decided"
    pdf = await ctx["far"].get(f"{S}/{j['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # ro'yxat: xodim faqat o'zinikini, HR hammasini
    assert (await ctx["far"].get(S)).json()["total"] == 1
    assert (await ctx["other"].get(S)).json()["total"] == 0
    assert (await ctx["hrd"].get(S, params={"kind": "application"})).json()["total"] == 1
    # bekor qilish: kutilayotgan arizani xodim bekor qiladi
    r2 = (await ctx["far"].post(f"{S}/applications", json={"subtype": "resign", "body": "Ishdan bo'shayman"})).json()
    assert (await ctx["far"].post(f"{S}/{r2['id']}/cancel")).json()["status"] == "cancelled"


async def test_order_sign_ack_and_verify(new_client):
    ctx = await setup(new_client)
    app_id = (await ctx["far"].post(f"{S}/applications", json={"subtype": "vacation", "body": "Ta'til", "start_date": "2026-12-01", "end_date": "2026-12-07"})).json()["id"]
    await ctx["hrm"].post(f"{S}/{app_id}/decide", json={"action": "approve"})
    assert (await ctx["far"].post(f"{S}/orders", json={"employee_id": ctx["emp"], "subtype": "vacation"})).status_code == 403
    o = await ctx["hrm"].post(f"{S}/orders", json={"employee_id": ctx["emp"], "subtype": "vacation", "start_date": "2026-12-01", "end_date": "2026-12-07", "related_id": app_id})
    assert o.status_code == 201, o.text
    oj = o.json()
    assert oj["status"] == "draft" and oj["number"] is None and "Far X" in oj["body"] and oj["can"]["edit"] and not oj["can"]["sign"]  # menejer imzolay olmaydi
    assert (await ctx["far"].get(f"{S}/{oj['id']}")).status_code == 404  # qoralamani xodim ko'rmaydi
    assert (await ctx["hrm"].put(f"{S}/{oj['id']}", json={"title": "Ta'til buyrug'i", "body": "1. Ta'til berilsin.\n2. Tabelga kiritilsin.", "start_date": "2026-12-01", "end_date": "2026-12-07"})).json()["title"] == "Ta'til buyrug'i"
    assert (await ctx["hrm"].post(f"{S}/{oj['id']}/sign", json={"password": PASSWORD})).status_code == 403
    assert (await ctx["hrd"].post(f"{S}/{oj['id']}/sign", json={"password": "noto'g'ri"})).json()["detail"]["code"] == "wrong_password"
    sg = await ctx["hrd"].post(f"{S}/{oj['id']}/sign", json={"password": PASSWORD})
    assert sg.status_code == 200, sg.text
    sj = sg.json()
    assert sj["status"] == "issued" and sj["number"].startswith("BY-") and sj["signed_by"] == "Hrd"
    assert any(n["kind"] == "staff.order_issued" for n in await notes(ctx["far"]))
    # imzolangach tahrirlab bo'lmaydi; xodim tanishadi
    assert (await ctx["hrm"].put(f"{S}/{oj['id']}", json={"title": "x" * 5, "body": "yangi matn"})).json()["detail"]["code"] == "not_editable"
    got = (await ctx["far"].get(f"{S}/{oj['id']}")).json()
    assert got["can"]["ack"] and got["acknowledged_at"] is None
    assert (await ctx["other"].post(f"{S}/{oj['id']}/ack")).status_code == 404
    ak = await ctx["far"].post(f"{S}/{oj['id']}/ack")
    assert ak.json()["acknowledged_at"] and not ak.json()["can"]["ack"]
    pdf = await ctx["far"].get(f"{S}/{oj['id']}/pdf", params={"lang": "ru"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # ochiq tekshiruv
    from sqlalchemy import select

    from app.models.hrdocs import StaffDocument

    async with SessionLocal() as s:
        code = (await s.scalar(select(StaffDocument).where(StaffDocument.id == oj["id"]))).code
    pub = new_client()
    v = await pub.get(f"/api/v1/public/staffdoc/{code}")
    assert v.status_code == 200
    vj = v.json()
    assert vj["valid"] and vj["intact"] and vj["number"] == sj["number"] and vj["employee"] == "Far X" or vj["employee"].startswith("Far")
    assert (await pub.get(f"/api/v1/public/staffdoc/{code}", params={"hash": vj["hash_prefix"]})).json()["hash_match"] is True
    assert (await pub.get("/api/v1/public/staffdoc/yoq")).status_code == 404
    # bekor qilish (HR)
    assert (await ctx["hrd"].post(f"{S}/{oj['id']}/cancel")).json()["status"] == "cancelled"


async def test_employee_feed(new_client):
    ctx = await setup(new_client)
    await ctx["far"].post(f"{S}/applications", json={"subtype": "other", "body": "Boshqa masala"})
    feed = await ctx["hrd"].get(f"{S}/employee/{ctx['emp']}/feed")
    assert feed.status_code == 200 and feed.json()["items"][0]["type"] == "application"
    assert (await ctx["far"].get(f"{S}/employee/{ctx['emp']}/feed")).status_code == 403
    assert (await ctx["aud"].get(f"{S}/employee/{ctx['emp']}/feed")).status_code == 200
