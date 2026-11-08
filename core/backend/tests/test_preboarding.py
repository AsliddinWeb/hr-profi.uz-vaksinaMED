import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.employees import Employee
from app.models.internship import InternshipEnrollment
from app.models.org import Position
from app.services import preboarding as svc
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

P = "/api/v1/preboarding"
YT = "https://www.youtube.com/watch?v=4PPQsAn6VjY"
SLIDES = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view"
QS = [{"text": "Retseptsiz antibiotik sotiladimi?", "options": ["Ha", "Yo'q", "Ba'zan", "Bilmayman"], "correct": [1]},
      {"text": "Kassa qachon yopiladi?", "options": ["Smena oxirida", "Tushlikda"], "correct": [0]}]  # fmt: skip


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def setup(new_client, monitoring=None):
    hr, _ = await as_user(new_client, "hrd", "hr_direktor")
    intern, uid = await as_user(new_client, "staj", "stajyor")
    async with SessionLocal() as s:
        far = Position(name="Farmasevt")
        mud = Position(name="Mudir")
        s.add_all([far, mud])
        await s.flush()
        s.add(Employee(last_name="Aliyeva", first_name="Laylo", full_name="Aliyeva Laylo", user_id=uid, position_id=far.id, status="active"))
        await s.commit()
        far_id, mud_id = far.id, mud.id
    r = await hr.post(f"{P}/tracks", json={"position_id": far_id, "pass_score": 50, **({"monitoring": monitoring} if monitoring else {})})
    assert r.status_code == 201, r.text
    return hr, intern, r.json(), far_id, mud_id


def stage_body(title, **kw):
    return {"title": title, "description": "Video, slayd va test", "audience": "all", "url": None, "slides_url": None, "questions": [], "published": True, **kw}


async def test_track_template_and_editing(new_client):
    hr, intern, track, far_id, mud_id = await setup(new_client)
    assert [s["title"][:9] for s in track["stages"]] == ["1-bosqich", "2-bosqich", "3-bosqich", "4-bosqich", "5-bosqich"]
    assert track["position"]["name"] == "Farmasevt" and "7 kunda" in track["description"]
    assert (await intern.post(f"{P}/tracks", json={"position_id": mud_id})).status_code == 403  # stajyor boshqara olmaydi
    # Bosqichga video, slayd va test
    sid = track["stages"][1]["id"]
    r = await hr.put(f"{P}/stages/{sid}", json=stage_body("2-bosqich: Apteka kirish asoslari", url=YT, slides_url=SLIDES, questions=QS))
    assert r.status_code == 200, r.text
    media = r.json()["media"]
    assert media["video"]["kind"] == "youtube" and media["video"]["id"] == "4PPQsAn6VjY" and media["video"]["thumb"]
    assert media["slides"]["embed"].endswith("/preview")
    assert (await hr.put(f"{P}/stages/{sid}", json=stage_body("x", url="javascript:alert(1)"))).json()["detail"]["code"] == "url_invalid"
    # Lavozimni almashtirish (admin)
    r = await hr.put(f"{P}/tracks/{track['id']}", json={"position_id": mud_id, "pass_score": 60, "monitoring": {"camera": True, "live": False, "record": True, "snapshots": True}})
    assert r.status_code == 200 and r.json()["position"]["name"] == "Mudir" and r.json()["monitoring"]["live"] is False
    r2 = (await hr.post(f"{P}/tracks", json={"position_id": far_id})).json()
    assert (await hr.put(f"{P}/tracks/{r2['id']}", json={"position_id": mud_id})).json()["detail"]["code"] == "track_exists"
    # Yangi bosqich qo'shish va o'chirish
    new = (await hr.post(f"{P}/tracks/{track['id']}/stages", json=stage_body("6-bosqich: qo'shimcha", published=False))).json()
    assert new["published"] is False and new["position"] == 5
    assert (await hr.delete(f"{P}/stages/{new['id']}")).status_code == 204


async def test_intern_flow_tracking_and_test(new_client):
    hr, intern, track, *_ = await setup(new_client)
    st = track["stages"]
    await hr.put(f"{P}/stages/{st[0]['id']}", json=stage_body(st[0]["title"]))  # faqat matn
    await hr.put(f"{P}/stages/{st[1]['id']}", json=stage_body(st[1]["title"], url=YT, slides_url=SLIDES, questions=QS, min_slides_seconds=30))
    await hr.put(f"{P}/stages/{st[2]['id']}", json=stage_body("3-bosqich: qoralama", published=False))

    my = (await intern.get(f"{P}/my")).json()
    assert my["program"]["position"] == "Farmasevt" and my["enrollment"]["status"] == "active"
    assert len(my["stages"]) == 4  # qoralama bosqich ko'rinmaydi
    assert [s["state"] for s in my["stages"][:2]] == ["available", "locked"]
    s1, s2 = my["stages"][0]["id"], my["stages"][1]["id"]
    assert "correct" not in my["stages"][1]["questions"][0]  # javoblar ko'rinmaydi
    assert (await intern.post(f"{P}/my/stages/{s2}/start")).json()["detail"]["code"] == "step_locked"
    assert (await intern.post(f"{P}/my/stages/{s1}/start")).json()["detail"]["code"] == "consent_required"
    assert (await intern.post(f"{P}/my/consent")).json()["enrollment"]["consent"]
    assert (await intern.post(f"{P}/my/stages/{s1}/done")).status_code == 200

    start = (await intern.post(f"{P}/my/stages/{s2}/start")).json()
    mid = start["monitor_id"]
    assert mid and start["monitoring"]["record"]
    # Test video/slayd ko'rilmaguncha yopiq
    assert (await intern.post(f"{P}/my/stages/{s2}/submit", json={"answers": {}})).json()["detail"]["code"] == "media_not_watched"
    # Kamera o'chiq bo'lsa vaqt hisoblanmaydi
    r = (await intern.post(f"{P}/my/stages/{s2}/tick", json={"kind": "video", "delta": 10, "pos": 10, "duration": 40, "monitor_id": mid, "camera_ok": False, "event": "camera_off"})).json()
    assert r["counted"] is False and r["stages"][1]["req"]["video"]["seen"] == 0
    for i in range(4):  # bir tickda ko'pi bilan 20 s
        await intern.post(f"{P}/my/stages/{s2}/tick", json={"kind": "video", "delta": 60, "pos": (i + 1) * 10, "duration": 40, "monitor_id": mid})
    for _ in range(2):
        r = (await intern.post(f"{P}/my/stages/{s2}/tick", json={"kind": "slides", "delta": 15, "monitor_id": mid})).json()
    req = r["stages"][1]["req"]
    assert req["video"]["done"] and req["video"]["seen"] == 80 and req["slides"]["done"] and not req["test"]["done"]

    qids = [q["id"] for q in r["stages"][1]["questions"]]
    bad = (await intern.post(f"{P}/my/stages/{s2}/submit", json={"answers": {qids[0]: [0], qids[1]: [1]}})).json()
    assert bad["passed"] is False and bad["score"] == 0 and set(bad["wrong"]) == set(qids)
    ok = (await intern.post(f"{P}/my/stages/{s2}/submit", json={"answers": {qids[0]: [1], qids[1]: [1]}})).json()
    assert ok["passed"] is True and ok["score"] == 50  # o'tish chegarasi 50%
    assert [s["state"] for s in ok["stages"][:3]] == ["done", "done", "available"]

    # Kamera yozuvi va surat
    webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 500
    assert (await intern.post(f"{P}/my/monitor/{mid}/clip", files={"file": ("c.webm", webm, "video/webm")})).status_code == 201
    assert (await intern.post(f"{P}/my/monitor/{mid}/clip", files={"file": ("x.exe", b"MZ\x90\x00" * 50, "video/webm")})).status_code == 415
    jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 300
    assert (await intern.post(f"{P}/my/monitor/{mid}/snapshot", files={"file": ("s.jpg", jpg, "image/jpeg")})).status_code == 201

    # HR natijalari va kuzatuv
    res = (await hr.get(f"{P}/tracks/{track['id']}/results")).json()["items"][0]
    assert res["employee"]["full_name"] == "Aliyeva Laylo" and res["consent"] and res["summary"]["done"] == 2
    sess = res["sessions"][0]
    assert sess["clips"] == 1 and sess["snapshots"] == 1 and sess["live"] is True
    assert any(e["kind"] == "camera_off" for e in sess["events"])
    det = (await hr.get(f"{P}/monitor/{sess['id']}")).json()
    assert len(det["clip_list"]) == 1 and len(det["snapshot_list"]) == 1
    clip = await hr.get(f"{P}/monitor/{sess['id']}/clip/0")
    assert clip.status_code == 200 and clip.content == webm
    assert (await intern.get(f"{P}/monitor/{sess['id']}")).status_code == 403  # stajyor boshqalarni ko'rmaydi
    # Sessiya tugadi: endi yuklab bo'lmaydi
    assert (await intern.post(f"{P}/my/monitor/{mid}/end")).status_code == 204
    assert (await intern.post(f"{P}/my/monitor/{mid}/snapshot", files={"file": ("s.jpg", jpg, "image/jpeg")})).status_code == 404


async def test_no_track_no_camera_and_helpers(new_client):
    hr, intern, track, far_id, mud_id = await setup(new_client, monitoring={"camera": False, "live": False, "record": False, "snapshots": False})
    st = (await intern.get(f"{P}/my")).json()["stages"][0]
    r = (await intern.post(f"{P}/my/stages/{st['id']}/start")).json()
    assert r["monitor_id"] is None and r["live"] is None  # kamera talab qilinmaydi: roziliksiz boshlanadi
    other, uid = await as_user(new_client, "boshqa", "stajyor")
    assert (await other.get(f"{P}/my")).json() is None  # xodim kartasi yo'q
    async with SessionLocal() as s:
        s.add(Employee(last_name="B", first_name="B", full_name="B B", user_id=uid, position_id=mud_id, status="active"))
        await s.commit()
    assert (await other.get(f"{P}/my")).json() is None  # Mudir lavozimida dastur yo'q
    async with SessionLocal() as s:
        assert await s.scalar(select(InternshipEnrollment.id).where(InternshipEnrollment.program_id == track["id"])) is not None
    assert svc.youtube_id("https://youtu.be/iOgkuZ1xilw") == "iOgkuZ1xilw"
    assert svc.youtube_id("https://www.youtube.com/shorts/iOgkuZ1xilw") == "iOgkuZ1xilw"
    assert svc.drive_id("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view?usp=sharing") == "1AbCdEfGhIjKlMnOp"
    assert (await hr.delete(f"{P}/tracks/{track['id']}")).status_code == 204  # stajyori bor: nofaol qilinadi
    assert all(t["id"] != track["id"] for t in (await hr.get(f"{P}/tracks")).json()["items"])
