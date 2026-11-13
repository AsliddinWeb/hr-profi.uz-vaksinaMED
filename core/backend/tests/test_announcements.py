import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.company import CompanySetting
from app.models.competency import Competency, PositionProfile
from app.models.org import Department, Position
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
R = "/api/v1/recruit"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def test_request_to_announcement_to_vacancy(new_client):
    hr, _ = await as_user(new_client, "hrann", "hr_direktor")
    head, head_id = await as_user(new_client, "boshann", "farmasevt")
    async with SessionLocal() as s:
        d = Department(name="Savdo", head_user_id=head_id)
        s.add(d)
        await s.flush()
        p = Position(name="Sotuvchi", department_id=d.id)
        s.add(p)
        await s.flush()
        did, pid = d.id, p.id
        s.add(PositionProfile(position_id=pid, status="approved", data={}))
        await s.merge(CompanySetting(key="recruit.ad_review", value="1"))
        await s.commit()
    card = {"duties": "Mijozlarga xizmat", "hard_skills": ["Kassa apparati"], "soft_skills": ["Xushmuomalalik"], "languages": ["rus"], "min_experience": 1}
    r = (await head.post(f"{R}/requests", json={"department_id": did, "position_id": pid, "count": 2, "reason": "Yangi do'kon", "salary_from": 5000000, "card": card})).json()
    async with SessionLocal() as s:
        names = set((await s.scalars(select(Competency.name))).all())
    assert {"Kassa apparati", "Xushmuomalalik", "rus"} <= names
    ok = (await hr.post(f"{R}/requests/{r['id']}/decide", json={"action": "approve"})).json()
    assert ok["status"] == "approved" and ok["vacancy_id"] is None
    lst = (await hr.get(f"{R}/announcements")).json()
    ann = lst["items"][0]
    assert lst["counts"]["draft"] == 1 and ann["status"] == "draft"
    full = (await hr.get(f"{R}/announcements/{ann['id']}")).json()
    assert "Kassa apparati" in full["text"] and "5 000 000" in full["text"] and "Mijozlarga xizmat" in full["text"]
    body = {"title": full["title"], "text": full["text"] + "\nQo'shimcha", "channels": [{"channel": "telegram", "targets": ["@ishbor", "@ishbor", "@vakansiya_uz"]}, {"channel": "hh_uz", "targets": []}]}
    saved = (await hr.put(f"{R}/announcements/{ann['id']}", json=body)).json()
    assert saved["channels"][0]["targets"] == ["@ishbor", "@vakansiya_uz"]
    assert (await head.post(f"{R}/announcements/{ann['id']}/approve")).status_code == 403
    done = (await hr.post(f"{R}/announcements/{ann['id']}/approve")).json()
    assert done["status"] == "approved" and done["vacancy_id"]
    v = (await hr.get(f"{R}/vacancies/{done['vacancy_id']}")).json()
    assert v["status"] == "open" and v["openings"] == 2
    assert (await hr.post(f"{R}/announcements/{ann['id']}/approve")).status_code == 409
