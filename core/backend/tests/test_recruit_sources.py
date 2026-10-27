import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.org import Position
from app.models.recruit import Application, Candidate, Vacancy
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

PH = "/api/v1/pharmacy"
RC = "/api/v1/recruit"
PUB = "/api/v1/public/apply"


async def as_user(new_client, login_name, role):
    uid = await make_user(login_name, role)
    c = new_client()
    assert (await login(c, login_name)).status_code == 200
    return c, uid


async def setup(new_client):
    hrd, hrd_id = await as_user(new_client, "hrd", "hr_direktor")
    hr, hr_id = await as_user(new_client, "hrm", "hr_menejer")
    coord, coord_id = await as_user(new_client, "coord", "koordinator")
    branch = (await hrd.post("/api/v1/branches", json={"number": 21, "name": "F21", "coordinator_user_id": coord_id})).json()
    async with SessionLocal() as s:
        p = Position(name="Farmasevt")
        s.add(p)
        await s.commit()
        pid = p.id
    return {"hrd": hrd, "hr": hr, "coord": coord, "branch": branch, "pid": pid, "hr_id": hr_id}


def need_body(ctx, **kw):
    return {"branch_id": ctx["branch"]["id"], "role": "pharmacist", "count": 2, "urgency": "urgent", "reason": "Xodim ketdi", "reason_type": "departure", "shift_note": "2-smena", "position_id": ctx["pid"], **kw}


async def test_need_approval_chain_opens_vacancy(new_client):
    ctx = await setup(new_client)
    await ctx["hrd"].put(f"{RC}/requirements/{ctx['pid']}", json={"requirements": "Tibbiy o'rta ma'lumot", "competencies": ["muloqot"], "ad_template": "E'lon: {title}\n{requirements}\n{link}"})
    n = (await ctx["coord"].post(f"{PH}/needs", json=need_body(ctx))).json()
    nid = n["id"]
    assert n["approval"] == "pending_hr" and n["vacancy_id"] is None

    # koordinator qaror chiqara olmaydi; HR menejer to'g'ridan-to'g'ri tasdiqlay olmaydi, faqat HRD ga uzatadi
    assert (await ctx["coord"].post(f"{PH}/needs/{nid}/decide", json={"action": "forward"})).status_code == 403
    assert (await ctx["hr"].post(f"{PH}/needs/{nid}/decide", json={"action": "approve"})).status_code == 403
    r = await ctx["hr"].post(f"{PH}/needs/{nid}/decide", json={"action": "forward", "note": "Maqul"})
    assert r.status_code == 200 and r.json()["approval"] == "pending_hrd"
    assert (await ctx["hr"].post(f"{PH}/needs/{nid}/decide", json={"action": "forward"})).status_code in (403, 409)

    r = await ctx["hrd"].post(f"{PH}/needs/{nid}/decide", json={"action": "approve", "note": "OK"})
    assert r.status_code == 200 and r.json()["approval"] == "approved" and r.json()["vacancy_id"]
    async with SessionLocal() as s:
        v = await s.get(Vacancy, r.json()["vacancy_id"])
        assert v.status == "open" and v.openings == 2 and v.requirements == "Tibbiy o'rta ma'lumot" and v.branch_id == ctx["branch"]["id"]
    assert (await ctx["hrd"].post(f"{PH}/needs/{nid}/decide", json={"action": "reject", "note": "x"})).json()["detail"]["code"] == "already_decided"


async def test_reject_needs_note_and_hrd_creates_directly(new_client):
    ctx = await setup(new_client)
    nid = (await ctx["coord"].post(f"{PH}/needs", json=need_body(ctx))).json()["id"]
    assert (await ctx["hr"].post(f"{PH}/needs/{nid}/decide", json={"action": "reject"})).json()["detail"]["code"] == "note_required"
    r = await ctx["hr"].post(f"{PH}/needs/{nid}/decide", json={"action": "reject", "note": "Shtat to'liq"})
    assert r.json()["approval"] == "rejected" and r.json()["status"] == "cancelled" and r.json()["vacancy_id"] is None
    # HRD o'zi yaratsa zanjir o'tkazib yuboriladi va vakansiya darhol ochiladi
    n = (await ctx["hrd"].post(f"{PH}/needs", json=need_body(ctx))).json()
    assert n["approval"] == "approved" and n["vacancy_id"]


async def test_channels_links_public_apply_and_report(new_client):
    ctx = await setup(new_client)
    nid = (await ctx["hrd"].post(f"{PH}/needs", json=need_body(ctx))).json()["vacancy_id"]
    vid = nid
    assert (await ctx["hr"].post(f"{RC}/vacancies/{vid}/channels", json={"channel": "hh_uz", "url": "javascript:alert(1)"})).json()["detail"]["code"] == "url_invalid"
    assert (await ctx["hr"].post(f"{RC}/vacancies/{vid}/channels", json={"channel": "hh_uz", "url": "https://hh.uz/vacancy/1"})).status_code == 201
    link = (await ctx["hr"].post(f"{RC}/vacancies/{vid}/links", json={"channel": "telegram", "label": "Kanal"})).json()
    code = link["code"]

    promo = (await ctx["hr"].get(f"{RC}/vacancies/{vid}/promo")).json()
    assert len(promo["channels"]) == 1 and promo["links"][0]["code"] == code and code in promo["ad"]

    anon = new_client()
    info = await anon.get(f"{PUB}/{code}")
    assert info.status_code == 200 and info.json()["title"].startswith("Farmasevt")
    assert (await anon.get(f"{PUB}/nope")).status_code == 404
    body = {"full_name": "Karimov Aziz", "phone": "+998901234567", "note": "Tajribam bor"}
    assert (await anon.post(f"{PUB}/{code}", json=body)).status_code == 201
    assert (await anon.post(f"{PUB}/{code}", json=body)).json().get("duplicate") is True
    assert (await anon.post(f"{PUB}/{code}", json={**body, "phone": "+998907654321", "website": "spam"})).json() == {"ok": True}
    assert (await anon.post(f"{PUB}/{code}", json={**body, "phone": "1234567"})).status_code == 400

    async with SessionLocal() as s:
        c = (await s.scalars(select(Candidate))).all()
        assert len(c) == 1 and c[0].source == "telegram"  # tuzoq maydon to'ldirilgan ariza yozilmagan
        a = (await s.scalars(select(Application))).one()
        assert a.source_link_id == link["id"] and a.stage == "new"

    rep = (await ctx["hr"].get(f"{RC}/sources", params={"vacancy_id": vid})).json()
    assert rep["total"] == 1 and rep["by_channel"][0]["channel"] == "telegram" and rep["by_channel"][0]["applications"] == 1 and rep["by_channel"][0]["clicks"] == 1
    assert rep["by_owner"][0]["owner"] == "Hrm"

    # o'chirilgan link ishlamaydi
    await ctx["hr"].post(f"{RC}/links/{link['id']}/deactivate")
    assert (await anon.get(f"{PUB}/{code}")).status_code == 404
