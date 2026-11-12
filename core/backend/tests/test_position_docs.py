import pytest

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.org import Department, Position
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
R = "/api/v1/position-docs"
SIG = "data:image/png;base64," + "A" * 200


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def test_position_documents_sign_and_upload(new_client):
    hr, _ = await as_user(new_client, "hrpd", "hr_direktor")
    emp_c, emp_uid = await as_user(new_client, "xodpd", "farmasevt")
    async with SessionLocal() as s:
        d = Department(name="Ombor")
        s.add(d)
        await s.flush()
        p = Position(name="Omborchi", department_id=d.id, duties=[{"title": "Kirim-chiqimni yuritish"}])
        s.add(p)
        await s.flush()
        e = Employee(last_name="Ali", first_name="V", full_name="Ali V", user_id=emp_uid, status="active", position_id=p.id, department_id=d.id)
        s.add(e)
        await s.commit()
        pid = p.id
    assert (await emp_c.get(f"{R}/positions/{pid}")).status_code == 403
    ins = (await hr.post(f"{R}/positions/{pid}/instruction")).json()
    assert ins["version"] == 1
    assert (await hr.put(f"{R}/positions/{pid}/required", json={"items": [{"kind": "passport", "title": "Pasport"}, {"kind": "photo", "title": "3x4 rasm"}, {"kind": "bad", "title": "x"}]})).json()["count"] == 2
    my = (await emp_c.get(f"{R}/my")).json()
    assert my["todo"] == 3 and "Kirim-chiqimni yuritish" in my["documents"][0]["body"]
    doc_id = my["documents"][0]["id"]
    assert (await emp_c.post(f"{R}/my/sign/{doc_id}", json={"signature": SIG})).status_code == 200
    assert (await emp_c.post(f"{R}/my/sign/{doc_id}", json={"signature": SIG})).status_code == 409
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    up = await emp_c.post(f"{R}/my/upload", data={"kind": "passport", "title": "Pasport"}, files={"file": ("p.png", png, "image/png")})
    assert up.status_code == 201, up.text
    assert up.json()["status"] == "pending"
    info = (await hr.get(f"{R}/positions/{pid}")).json()
    assert info["documents"][0]["signed"] == 1 and info["employees"][0]["uploads"]["passport"]["status"] == "pending"
    assert (await hr.post(f"{R}/uploads/{up.json()['id']}/review", json={"action": "return"})).status_code == 400
    assert (await hr.post(f"{R}/uploads/{up.json()['id']}/review", json={"action": "approve"})).json()["status"] == "approved"
    # yo'riqnoma yangilansa — yangi versiya, imzo qaytadan kerak
    async with SessionLocal() as s:
        pos = await s.get(Position, pid)
        pos.duties = [{"title": "Inventarizatsiya"}]
        await s.commit()
    assert (await hr.post(f"{R}/positions/{pid}/instruction")).json()["version"] == 2
    my = (await emp_c.get(f"{R}/my")).json()
    assert my["documents"][0]["signed_at"] is None and my["todo"] == 2
