import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import select, update

from app.config import get_settings
from app.db import SessionLocal
from app.face import crypto
from app.face.engine import FrameResult
from app.face.liveness import classify, verify_liveness
from app.models.employees import Employee
from app.models.face import FaceTemplate
from app.services import face as face_svc
from tests.test_attendance import FAR, LAT, LNG, NEAR, Clock, as_user  # noqa: F401

F = "/api/v1/face"
VERSION = get_settings().face_consent_version
needs_db = pytest.mark.skipif("not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak")

YAW = {"center": 0.0, "left": 0.5, "right": -0.5}


def frame(person: str, yaw: float = 0.0, **kw) -> tuple[str, bytes, str]:
    return ("frames", json.dumps({"id": person, "yaw": yaw, **kw}).encode(), "image/jpeg")


def sequence(person: str, steps: list[str], **kw):
    """Challenge qadamlariga mos kadrlar (har qadam 2 kadr)."""
    return [frame(person, YAW[s] + d, **kw) for s in steps for d in (0.0, 0.02)]


def files(frames):
    return [("frames", (f"f{i}.jpg", data, ct)) for i, (_, data, ct) in enumerate(frames)]


async def new_challenge(c, purpose):
    r = await c.post(f"{F}/challenge", json={"purpose": purpose})
    assert r.status_code == 200, r.text
    return r.json()


async def give_consent(c):
    r = await c.post(f"{F}/consent", json={"version": VERSION})
    assert r.status_code == 200, r.text


async def enroll(c, person="alice", **kw):
    ch = await new_challenge(c, "enroll")
    return await c.post(f"{F}/enroll", data={"challenge_id": ch["id"]}, files=files(sequence(person, ch["steps"], **kw)))


async def verify_punch(c, person="alice", extra=None, frames_fn=sequence):
    ch = await new_challenge(c, "verify")
    return await c.post(f"{F}/punch", data={"challenge_id": ch["id"], **(extra or {})}, files=files(frames_fn(person, ch["steps"])))


async def employee_user(new_client, login_name, *, branch_id=None, role="farmasevt"):
    c, uid = await as_user(new_client, login_name, role)
    async with SessionLocal() as s:
        emp = Employee(last_name=login_name.title(), first_name="X", full_name=f"{login_name.title()} X", user_id=uid, branch_id=branch_id, status="active")
        s.add(emp)
        await s.commit()
        return c, emp.id


# --- Unit -------------------------------------------------------------------------------


def test_encryption_roundtrip_and_binding():
    vec = np.random.default_rng(1).normal(size=128).astype(np.float32)
    blob = crypto.encrypt_vector(vec, 5)
    assert vec.tobytes() not in blob and len(blob) > 12 + 128 * 4
    assert np.allclose(crypto.decrypt_vector(blob, 5), vec)
    with pytest.raises(Exception):  # noqa: B017  (boshqa xodim AAD si)
        crypto.decrypt_vector(blob, 6)


def _fr(person_vec, yaw, q=0.8):
    return FrameResult(True, None, yaw, q, person_vec)


def test_liveness_rules():
    rng = np.random.default_rng(3)
    a = rng.normal(size=128).astype(np.float32)
    a /= np.linalg.norm(a)
    b = rng.normal(size=128).astype(np.float32)
    b /= np.linalg.norm(b)
    steps = ["center", "left", "right"]
    good = [_fr(a, 0.0), _fr(a, 0.02), _fr(a, 0.5), _fr(a, 0.45), _fr(a, -0.5), _fr(a, -0.4)]
    assert verify_liveness(steps, good) == (True, None)
    # statik rasm: burilish yo'q
    assert verify_liveness(steps, [_fr(a, 0.01 * i) for i in range(6)]) == (False, "challenge_failed")
    # tartib noto'g'ri
    assert verify_liveness(["center", "right", "left"], good) == (False, "challenge_failed")
    # kadrlar yetarli emas
    assert verify_liveness(steps, good[:3]) == (False, "not_enough_frames")
    # o'rtada boshqa odam
    swapped = good[:3] + [_fr(b, -0.5), _fr(b, -0.4)] + [good[0]]
    assert verify_liveness(steps, swapped) == (False, "different_person")
    assert classify(0.1) == "center" and classify(0.4) == "left" and classify(-0.4) == "right" and classify(0.2) is None


# --- Rozilik va ro'yxatga olish ---------------------------------------------------------


@needs_db
async def test_consent_and_enroll_flow(new_client):
    c, emp_id = await employee_user(new_client, "ali")
    r = await c.post(f"{F}/challenge", json={"purpose": "enroll"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "consent_required"
    r = await c.post(f"{F}/consent", json={"version": "old"})
    assert r.json()["detail"]["code"] == "consent_version_mismatch"
    await give_consent(c)

    r = await enroll(c)
    assert r.status_code == 200, r.text
    assert r.json()["poses"] == ["center", "left", "right"]
    st = (await c.get(f"{F}/status")).json()
    assert st["enrolled"] and st["consent"]["given"] and st["retention_days"] == get_settings().face_retention_days

    async with SessionLocal() as s:
        rows = (await s.scalars(select(FaceTemplate).where(FaceTemplate.employee_id == emp_id))).all()
        assert len(rows) == 3 and all(len(r.vector_enc) > 128 * 4 for r in rows)  # shifrlangan

    # rozilikni qaytarish: shablonlar darhol o'chadi
    assert (await c.delete(f"{F}/consent")).status_code == 204
    st = (await c.get(f"{F}/status")).json()
    assert not st["enrolled"] and not st["consent"]["given"] and st["consent"]["revoked_at"]
    assert (await c.post(f"{F}/challenge", json={"purpose": "verify"})).json()["detail"]["code"] == "consent_required"


@needs_db
async def test_enroll_rejections(new_client):
    c, _ = await employee_user(new_client, "ali")
    await give_consent(c)
    # statik rasm (burilish yo'q)
    ch = await new_challenge(c, "enroll")
    r = await c.post(f"{F}/enroll", data={"challenge_id": ch["id"]}, files=files([frame("alice", 0.0) for _ in range(6)]))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "liveness_failed" and r.json()["detail"]["reason"] == "challenge_failed"
    # sifatsiz kadrlar
    ch = await new_challenge(c, "enroll")
    r = await c.post(f"{F}/enroll", data={"challenge_id": ch["id"]}, files=files([frame("a", reason="blurry") for _ in range(6)]))
    assert r.json()["detail"]["reason"] == "not_enough_frames" and r.json()["detail"]["hint"] == "blurry"
    # challenge bir martalik va boshqa maqsadga yaroqsiz
    ch = await new_challenge(c, "enroll")
    ok = files(sequence("alice", ch["steps"]))
    assert (await c.post(f"{F}/enroll", data={"challenge_id": ch["id"]}, files=ok)).status_code == 200
    r = await c.post(f"{F}/enroll", data={"challenge_id": ch["id"]}, files=ok)
    assert r.json()["detail"]["code"] == "challenge_invalid"
    ch = await new_challenge(c, "verify")
    r = await c.post(f"{F}/enroll", data={"challenge_id": ch["id"]}, files=ok)
    assert r.json()["detail"]["code"] == "challenge_invalid"


@needs_db
async def test_duplicate_face_rejected_and_audited(new_client):
    a, _ = await employee_user(new_client, "ali")
    b, bid = await employee_user(new_client, "bob")
    for c in (a, b):
        await give_consent(c)
    assert (await enroll(a, "alice")).status_code == 200
    r = await enroll(b, "alice")  # do'stining yuzi
    assert r.status_code == 409 and r.json()["detail"]["code"] == "face_already_enrolled"
    assert "matched" not in json.dumps(r.json())  # boshqa xodim kimligi oshkor bo'lmaydi
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    audit = (await hr.get("/api/v1/audit", params={"action": "face.duplicate"})).json()
    assert audit["total"] == 1
    assert (await enroll(b, "bobby")).status_code == 200  # boshqa yuz muvaffaqiyatli


# --- Yuz orqali davomat -----------------------------------------------------------------


@needs_db
async def test_face_punch_match_and_mismatch(new_client, monkeypatch):
    clock = Clock()
    monkeypatch.setattr("app.services.attendance.now", clock)
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    branch = (await hr.post("/api/v1/branches", json={"number": 7, "name": "F7", "latitude": LAT, "longitude": LNG, "geofence_radius_m": 100})).json()
    shift = (await hr.post("/api/v1/schedule/shifts", json={"name": "K", "start_time": "09:00", "end_time": "18:00", "late_grace_minutes": 10})).json()
    await hr.post("/api/v1/schedule/groups", json={"name": "Ofis", "default_shift_id": shift["id"], "weekly_off_days": [6], "is_default": True})
    c, _ = await employee_user(new_client, "ali", branch_id=branch["id"])
    await give_consent(c)
    assert (await enroll(c, "alice")).status_code == 200

    clock.set("2026-11-02 09:20")
    r = await verify_punch(c, "alice", NEAR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["action"] == "check_in" and body["record"]["in_method"] == "face" and body["record"]["late_minutes"] == 20 and body["score"] > 0.7

    # boshqa odam (egasining nomidan belgilashga urinish)
    clock.set("2026-11-02 12:00")
    r = await verify_punch(c, "mallory", NEAR)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "face_mismatch"
    # geofence yuz orqali ham amal qiladi
    r = await verify_punch(c, "alice", FAR)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "outside_geofence"
    # statik rasm
    r = await verify_punch(c, "alice", NEAR, frames_fn=lambda p, s: [frame(p, 0.0) for _ in range(6)])
    assert r.json()["detail"]["code"] == "liveness_failed"

    clock.set("2026-11-02 17:00")
    r = await verify_punch(c, "alice", NEAR)
    assert r.json()["action"] == "check_out"

    d = (await hr.get("/api/v1/face/employees")).json()
    assert d["items"][0]["state"] in ("enrolled", "none")


@needs_db
async def test_face_lockout_after_repeated_failures(new_client):
    c, _ = await employee_user(new_client, "ali")
    await give_consent(c)
    await enroll(c, "alice")
    for _ in range(8):
        r = await verify_punch(c, "mallory", None)
        assert r.json()["detail"]["code"] == "face_mismatch"
    r = await c.post(f"{F}/challenge", json={"purpose": "verify"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "face_locked"


# --- Boshqaruv, saqlash muddati, o'lchov ------------------------------------------------


@needs_db
async def test_admin_views_are_status_only_and_audited(new_client):
    c, emp_id = await employee_user(new_client, "ali")
    await give_consent(c)
    await enroll(c, "alice")
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    lst = (await hr.get(f"{F}/employees", params={"state": "enrolled"})).json()
    assert lst["total"] == 1 and lst["items"][0]["templates"] == 3
    detail = (await hr.get(f"{F}/employees/{emp_id}")).json()
    dumped = json.dumps(detail)
    assert "vector" not in dumped and detail["state"] == "enrolled" and len(detail["templates"]) == 3
    assert (await hr.get("/api/v1/audit", params={"action": "face.view"})).json()["total"] == 1

    # ruxsatlar
    assert (await c.get(f"{F}/employees")).status_code == 403
    assert (await c.get(f"{F}/evaluation")).status_code == 403
    mgr, _ = await as_user(new_client, "m", "hr_menejer")
    assert (await mgr.get(f"{F}/employees")).status_code == 200
    assert (await mgr.get(f"{F}/evaluation")).status_code == 403  # face.evaluate faqat HR direktorda

    assert (await hr.delete(f"{F}/employees/{emp_id}/templates", params={"reason": "ab"})).status_code == 422
    assert (await hr.delete(f"{F}/employees/{emp_id}/templates", params={"reason": "Ishdan ketdi"})).status_code == 204
    assert (await hr.get(f"{F}/employees/{emp_id}")).json()["state"] == "consent_only"


@needs_db
async def test_retention_purge(new_client):
    a, aid = await employee_user(new_client, "ali")
    b, bid = await employee_user(new_client, "bob")
    d, did = await employee_user(new_client, "dina")
    for c, person in ((a, "p1"), (b, "p2"), (d, "p3")):
        await give_consent(c)
        assert (await enroll(c, person)).status_code == 200
    old = datetime.now(UTC) - timedelta(days=get_settings().face_retention_days + 5)
    async with SessionLocal() as s:
        await s.execute(update(FaceTemplate).where(FaceTemplate.employee_id == aid).values(created_at=old, last_verified_at=None))
        await s.execute(update(Employee).where(Employee.id == bid).values(status="dismissed", dismissal_date=(datetime.now(UTC) - timedelta(days=40)).date()))
        res = await face_svc.purge_templates(s)
    assert res == {"expired": 3, "dismissed": 3, "revoked": 0}
    async with SessionLocal() as s:
        left = {t.employee_id for t in (await s.scalars(select(FaceTemplate))).all()}
    assert left == {did}


@needs_db
async def test_evaluation_far_frr(new_client):
    a, _ = await employee_user(new_client, "ali")
    b, _ = await employee_user(new_client, "bob")
    for c, person in ((a, "p1"), (b, "p2")):
        await give_consent(c)
        await enroll(c, person)
    await verify_punch(a, "p1")
    await verify_punch(a, "zzz")
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    ev = (await hr.get(f"{F}/evaluation")).json()
    assert ev["enrolled_employees"] == 2 and ev["impostor_pairs"] == 1 and ev["genuine_attempts"] == 2
    row = next(r for r in ev["table"] if r["threshold"] == 0.4)
    assert row["far"] == 0.0 and row["frr"] == 0.5  # 1 ta haqiqiy rad etildi (zzz mos kelmadi)
    assert ev["enough_data"] is False and ev["recommended"] is None


# --- Haqiqiy dvigatel (OpenCV) ----------------------------------------------------------


def _real_engine():
    import os

    model_dir = os.environ.get("FACE_MODEL_DIR", "/opt/models")
    if not os.path.exists(os.path.join(model_dir, "face_recognition_sface_2021dec.onnx")):
        pytest.skip("Yuz modellari topilmadi")
    from app.face.engine import OpenCVEngine

    return OpenCVEngine(model_dir)


def test_real_engine_detects_and_matches(tmp_path):
    import cv2

    eng = _real_engine()
    img = cv2.imread("tests/data/astronaut.png")  # NASA, public domain
    head = cv2.resize(img[0:300, 120:420], None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", head)
    r1 = eng.analyze(buf.tobytes())
    assert r1.ok, r1.reason
    assert abs(r1.yaw) < 0.5 and r1.embedding.shape == (128,) and abs(np.linalg.norm(r1.embedding) - 1) < 1e-4
    # bir xil yuzning boshqa o'lcham/siqish varianti: yuqori o'xshashlik
    small = cv2.resize(head, None, fx=0.8, fy=0.8, interpolation=cv2.INTER_AREA)
    ok, buf2 = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
    r2 = eng.analyze(buf2.tobytes())
    assert r2.ok, r2.reason
    assert float(r1.embedding @ r2.embedding) > 0.8
    # yuzsiz rasm va yaroqsiz fayl
    blank = np.full((400, 400, 3), 128, np.uint8)
    assert eng.analyze(cv2.imencode(".jpg", blank)[1].tobytes()).reason == "no_face"
    assert eng.analyze(b"not an image").reason == "image_invalid"
