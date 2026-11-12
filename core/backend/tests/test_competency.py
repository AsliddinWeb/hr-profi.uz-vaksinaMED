import pytest

from app.db import SessionLocal
from app.models.org import Department, Position
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")
R = "/api/v1/recruit"


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


FULL = {
    "general": {"title": "Marketing menejeri"}, "goal": "Brendni rivojlantirish", "functions": ["Kampaniyalar"],
    "education": {"level": "Oliy"}, "kpi": [{"name": "Lead", "target": "100"}], "portrait": "Faol, kreativ",
}


async def test_profile_required_before_request(new_client):
    hr, _ = await as_user(new_client, "hrd", "hr_direktor")
    head, head_id = await as_user(new_client, "bosh", "farmasevt")
    far, _ = await as_user(new_client, "far", "farmasevt")
    async with SessionLocal() as s:
        d = Department(name="Marketing", head_user_id=head_id)
        p = Position(name="Marketing menejeri")
        s.add_all([d, p])
        await s.commit()
        did, pid = d.id, p.id
    assert (await far.post(f"{R}/competencies", json={"name": "SQL", "category": "hard"})).status_code == 403
    ids = {}
    for name, cat in (("Raqamli marketing", "hard"), ("Muloqot", "soft"), ("Jamoa boshqaruvi", "management")):
        r = await hr.post(f"{R}/competencies", json={"name": name, "category": cat})
        assert r.status_code == 201, r.text
        ids[cat] = r.json()["id"]
    assert (await hr.post(f"{R}/competencies", json={"name": "muloqot", "category": "soft"})).status_code == 409
    lst = (await hr.get(f"{R}/competencies", params={"category": "hard"})).json()
    assert lst["counts"]["hard"] == 1 and lst["counts"]["soft"] == 1 and lst["total"] == 1

    # profil yo'q -> zayafka bloklanadi
    body = {"department_id": did, "position_id": pid, "count": 1}
    assert (await head.post(f"{R}/requests", json=body)).json()["detail"]["code"] == "profile_not_approved"

    prof = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    assert prof["status"] == "draft" and prof["version"] == 1 and prof["can"]["edit"]
    comps = [{"competency_id": i, "required_level": 3, "ideal_level": 4} for i in ids.values()]
    half = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": {"goal": "x"}, "competencies": comps[:1]})).json()
    assert 0 < half["filled_pct"] < 100
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "submit"})).json()["detail"]["code"] == "profile_incomplete"
    full = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": FULL, "competencies": comps})).json()
    assert full["filled_pct"] == 100 and len(full["competencies"]) == 3
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "submit"})).json()["status"] == "pending"
    ap = (await hr.get(f"{R}/approvals")).json()
    assert ap["counts"]["profile"] == 1 and ap["items"][0]["code"] == f"PP-{prof['id']:03d}"
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "return"})).json()["detail"]["code"] == "note_required"
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "approve"})).json()["status"] == "approved"

    got = (await head.get(f"{R}/profiles/approved/{pid}")).json()
    assert got["profile"]["version"] == 1 and got["required"] is True
    r = await head.post(f"{R}/requests", json=body)
    assert r.status_code == 201, r.text
    dash = (await hr.get(f"{R}/competency-dashboard")).json()
    assert dash["approved"] == 1 and dash["competencies"] == 3 and dash["pending_requests"] == 1
    # yangi versiya oldingidan nusxa
    v2 = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    assert v2["version"] == 2 and len(v2["competencies"]) == 3
    lst = (await hr.get(f"{R}/profiles")).json()["items"]
    assert any(i["position"]["id"] == pid and i["profile"]["version"] == 2 for i in lst)


async def test_overview(new_client):
    hr, _ = await as_user(new_client, "hrov", "hr_direktor")
    r = await hr.get(f"{R}/overview", params={"days": 30})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["dynamics"]) == 6 and d["funnel"][0]["stage"] == "requests" and "deltas" in d


async def test_funnel_report(new_client):
    hr, _ = await as_user(new_client, "hrfr", "hr_direktor")
    r = await hr.get(f"{R}/funnel-report", params={"days": 90})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [s["stage"] for s in d["stages"]] == ["requests", "vacancies", "found", "screening", "interview", "test", "offer", "hired"]
    assert set(d["kpi"]) == {"candidates", "hired", "conversion", "avg_close_days"}


async def test_ai_fill_and_review(new_client, monkeypatch):
    import json as _json

    from app.services import ai

    hr, _ = await as_user(new_client, "hrai", "hr_direktor")
    async with SessionLocal() as s:
        p = Position(name="AXO boshlig'i")
        s.add(p)
        await s.commit()
        pid = p.id
    sql = (await hr.post(f"{R}/competencies", json={"name": "Byudjetlash", "category": "hard"})).json()["id"]
    prof = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    fill = {
        "general": {"title": "AXO boshlig'i", "grade": "M2"}, "goal": "Ofis xo'jaligini ta'minlash", "functions": ["Ta'minotni rejalash", 5],
        "daily": {"tools": ["Excel", "1C"], "routine": [{"time": "09:00", "task": "Buyurtmalarni ko'rish"}]},
        "kpi": [{"name": "Xarajat", "target": "-5%"}], "portrait": "Tartibli",
        "competencies": [{"name": "byudjetlash", "category": "hard", "required_level": 4, "ideal_level": 5}, {"name": "Muzokara", "category": "soft", "required_level": 9}, {"name": "x", "category": "bad"}],
    }
    review = {"score": 60, "summary": "KPI kam", "suggestions": [
        {"step": "kpi", "title": "Muddat KPI", "reason": "yo'q", "add": {"name": "Muddatida bajarish", "target": "95%"}},
        {"step": "hard", "title": "Xarid", "add": {"name": "Xarid jarayoni", "required_level": 3}},
        {"step": "nope", "title": "x"},
    ]}
    answers = iter([_json.dumps(fill), "```json\n" + _json.dumps(review) + "\n```"])

    async def fake_run(db, auth, feature, system, user, **kw):
        assert feature == "profile" and "<data>" in user
        return next(answers), "test"

    monkeypatch.setattr(ai, "run", fake_run)
    f = (await hr.post(f"{R}/profiles/{prof['id']}/ai-fill", json={"text": "Ofis xo'jaligi, xarid, ta'mirlash"})).json()
    assert f["data"]["functions"] == ["Ta'minotni rejalash"] and f["data"]["daily"]["tools"] == ["Excel", "1C"]
    by = {c["name"]: c for c in f["competencies"]}
    assert by["byudjetlash"]["competency_id"] == sql and by["Muzokara"]["competency_id"] is None and by["Muzokara"]["required_level"] == 5 and len(by) == 2
    # yangi kompetensiya nomi bilan saqlash -> bazaga qo'shiladi
    saved = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": f["data"], "competencies": f["competencies"]})).json()
    assert {c["name"] for c in saved["competencies"]} == {"Byudjetlash", "Muzokara", "Excel", "1C"} and saved["data"]["daily"]["routine"][0]["time"] == "09:00"
    r = (await hr.post(f"{R}/profiles/{prof['id']}/ai-review", json={"data": saved["data"], "competencies": saved["competencies"]})).json()
    assert r["score"] == 60 and [x["step"] for x in r["suggestions"]] == ["kpi", "hard"] and r["suggestions"][1]["add"]["category"] == "hard"


async def test_extract_text_from_files(new_client):
    import io
    import zipfile

    from openpyxl import Workbook

    hr, _ = await as_user(new_client, "hrfile", "hr_direktor")
    wb = Workbook()
    wb.active.append(["Vazifa", "Ombor hisobi"])
    xb = io.BytesIO()
    wb.save(xb)
    r = (await hr.post(f"{R}/profiles/extract-text", files={"file": ("a.xlsx", xb.getvalue())})).json()
    assert "Ombor hisobi" in r["text"]
    db = io.BytesIO()
    with zipfile.ZipFile(db, "w") as z:
        z.writestr("word/document.xml", "<w:document><w:p><w:t>Kun tartibi</w:t></w:p></w:document>")
    assert "Kun tartibi" in (await hr.post(f"{R}/profiles/extract-text", files={"file": ("b.docx", db.getvalue())})).json()["text"]
    assert (await hr.post(f"{R}/profiles/extract-text", files={"file": ("c.exe", b"x")})).json()["detail"]["code"] == "unsupported_file"


async def test_profile_additions_land_in_base(new_client):
    hr, _ = await as_user(new_client, "hrsync", "hr_direktor")
    async with SessionLocal() as s:
        p = Position(name="Omborchi")
        s.add(p)
        await s.commit()
        pid = p.id
    prof = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    data = {"daily": {"tools": ["Excel", "1C"]}, "education": {"field": "Logistika", "experience": "2 yil omborda", "languages": "rus, ingliz"}}
    saved = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": data, "competencies": [{"name": "Inventarizatsiya", "category": "hard"}]})).json()
    cats = {(c["category"], c["name"]) for c in saved["competencies"]}
    assert {("hard", "Inventarizatsiya"), ("knowledge", "Excel"), ("knowledge", "1C"), ("knowledge", "Logistika"), ("knowledge", "rus"), ("knowledge", "ingliz"), ("experience", "2 yil omborda")} == cats
    kb = (await hr.get(f"{R}/competencies", params={"category": "knowledge"})).json()
    excel = next(i for i in kb["items"] if i["name"] == "Excel")
    assert excel["positions"] == 1 and excel["position_list"][0]["name"] == "Omborchi"
    # dastur ro'yxatdan olib tashlansa, bog'lanish ham olinadi (qayta saqlashda)
    data["daily"]["tools"] = ["Excel"]
    again = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": data, "competencies": saved["competencies"]})).json()
    assert ("knowledge", "1C") not in {(c["category"], c["name"]) for c in again["competencies"]}


async def test_ai_fill_fallback_without_key(new_client):
    hr, _ = await as_user(new_client, "hrfb", "hr_direktor")
    async with SessionLocal() as s:
        p = Position(name="AXO")
        s.add(p)
        await s.commit()
        pid = p.id
    prof = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    text = "- Davlat idoralari bilan ishlash.\n- Kommunal xarajatlarni nazorat qilish, Excel va 1C da hisob.\nqisqa"
    r = (await hr.post(f"{R}/profiles/{prof['id']}/ai-fill", json={"text": text})).json()
    assert r["fallback"] is True and len(r["data"]["functions"]) == 2 and r["data"]["daily"]["tools"] == ["Excel", "1C"]


async def test_management_not_applicable_completes_profile(new_client):
    hr, _ = await as_user(new_client, "hrna", "hr_direktor")
    async with SessionLocal() as s:
        p = Position(name="Rekruter")
        s.add(p)
        await s.commit()
        pid = p.id
    prof = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    comps = [{"name": "Saralash", "category": "hard"}, {"name": "Muloqot", "category": "soft"}]
    r = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": FULL, "competencies": comps})).json()
    assert r["filled_pct"] == 89
    r = (await hr.put(f"{R}/profiles/{prof['id']}", json={"data": {**FULL, "management_na": True}, "competencies": comps})).json()
    assert r["filled_pct"] == 100
    assert (await hr.post(f"{R}/profiles/{prof['id']}/action", json={"action": "submit"})).json()["status"] == "pending"


async def test_competencies_by_position(new_client):
    hr, _ = await as_user(new_client, "hrbp", "hr_direktor")
    async with SessionLocal() as s:
        p = Position(name="Rekruter")
        s.add(p)
        await s.commit()
        pid = p.id
    prof = (await hr.post(f"{R}/profiles", json={"position_id": pid})).json()
    await hr.put(f"{R}/profiles/{prof['id']}", json={"data": {"daily": {"tools": ["Excel"]}}, "competencies": [{"name": "Saralash", "category": "hard"}, {"name": "Muloqot", "category": "soft"}]})
    items = (await hr.get(f"{R}/competencies/by-position")).json()["items"]
    row = next(i for i in items if i["position"]["id"] == pid)
    assert row["profile_id"] == prof["id"] and row["counts"]["hard"] == 1 and row["counts"]["knowledge"] == 1 and row["total"] == 3
