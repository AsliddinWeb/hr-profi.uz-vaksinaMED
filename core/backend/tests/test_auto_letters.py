import base64
import struct
import zlib
from datetime import date

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.letters import ExplanationLetter
from app.models.penalties import Penalty, PenaltyRuleVersion
from app.services import auto_letters as svc
from app.services.penalties import current_rules, scan_day
from tests.test_attendance import API, NEAR, as_user, clock, setup_basic  # noqa: F401

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

L = "/api/v1/letters"
REASON = "Avtobus kech keldi, yo'lda tirbandlik bo'ldi va mudirni oldindan ogohlantirdim"


def png(w: int = 60, h: int = 30) -> str:
    """Haqiqiy (kichik) PNG data URL: imzo sifatida yuboriladi."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + bytes((x * 7 + y * 3) % 256 for x in range(w * 3)) for y in range(h))
    raw = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(raw).decode()


@pytest.fixture(autouse=True)
def _letters_clock(monkeypatch, clock):  # noqa: F811
    monkeypatch.setattr("app.api.letters.now", clock)
    return clock


async def late_punch(pc, clock):  # noqa: F811
    clock.set("2026-11-02 09:32")
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.status_code == 200, r.text
    return r.json()


async def test_late_punch_creates_letter_and_pending_penalty(new_client, clock):  # noqa: F811
    _, pc, ctx = await setup_basic(new_client)
    body = await late_punch(pc, clock)
    assert body["record"]["late_minutes"] == 32 and body["letter_id"]

    async with SessionLocal() as s:
        p = await s.scalar(select(Penalty).where(Penalty.employee_id == ctx["emp_id"]))
        letter = await s.get(ExplanationLetter, body["letter_id"])
    assert p.status == "pending" and p.source == "auto" and p.incident_type == "late" and p.step == 1
    assert letter.auto and letter.status == "requested" and letter.penalty_id == p.id
    f = letter.facts
    assert (f["planned_start"], f["check_in"], f["late_minutes"], f["late_grace"], f["month_count"]) == ("09:00", "09:32", 32, 10, 1)
    assert f["branch"] == "Filial 7" and f["shift"] == "Kunduzgi" and len(f["steps"]) == 6 and f["next_step"] == 2

    pending = (await pc.get(f"{L}/auto/pending")).json()
    assert pending["id"] == letter.id and pending["verify_url"] is None
    doc = pending["document"]
    assert "09:32" in doc["incident"] and "32 daqiqa" in doc["incident"] and "1-qoidabuzarlik" in doc["subtitle"]
    assert "10 daqiqa imtiyoz" in doc["basis"]
    # QR hali yo'q
    assert (await pc.get(f"{L}/{letter.id}/auto/qr")).status_code == 409


async def test_checkin_blocked_until_signed(new_client, clock):  # noqa: F811
    _, pc, _ = await setup_basic(new_client)
    body = await late_punch(pc, clock)
    lid = body["letter_id"]
    # o'sha kunning ketishi bloklanmaydi
    clock.set("2026-11-02 18:05")
    assert (await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})).json()["action"] == "check_out"
    # keyingi kunning kelishi: xat imzolanmagan
    clock.set("2026-11-03 08:55")
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "letter_pending" and r.json()["detail"]["letter_id"] == lid

    # 1-qadam: sabab qisqa / o'qilmagan
    assert (await pc.post(f"{L}/{lid}/auto/confirm", json={"explanation": "kech qoldim", "read": True})).json()["detail"]["code"] == "explanation_short"
    assert (await pc.post(f"{L}/{lid}/auto/confirm", json={"explanation": REASON, "read": False})).json()["detail"]["code"] == "read_required"
    # imzo tasdiqlashdan oldin bo'lmaydi
    assert (await pc.post(f"{L}/{lid}/auto/sign", json={"signature": png()})).json()["detail"]["code"] == "letter_not_confirmed"
    r = await pc.post(f"{L}/{lid}/auto/confirm", json={"explanation": REASON, "read": True})
    assert r.status_code == 200 and r.json()["confirmed_at"] and r.json()["verify_url"].endswith(r.json()["code"])
    qr = await pc.get(f"{L}/{lid}/auto/qr")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg")

    # 3-qadam: noto'g'ri imzo, keyin to'g'ri
    assert (await pc.post(f"{L}/{lid}/auto/sign", json={"signature": "data:image/png;base64,QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="})).json()["detail"]["code"] == "signature_invalid"
    r = await pc.post(f"{L}/{lid}/auto/sign", json={"signature": png()})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "submitted" and out["signature_image"].startswith("data:image/png") and out["submitted_at"]
    assert (await pc.get(f"{L}/auto/pending")).json() is None
    async with SessionLocal() as s:
        letter = await s.get(ExplanationLetter, lid)
    assert letter.signature["method"] == "drawn" and letter.content_hash and REASON in letter.snapshot["body"]

    # endi «Keldim» ochiq
    clock.set("2026-11-03 08:56")
    assert (await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})).json()["action"] == "check_in"
    # ochiq tekshiruv ishlaydi
    v = (await pc.get(f"/api/v1/public/letters/{letter.code}")).json()
    assert v["valid"] and v["intact"]


async def test_other_user_cannot_act_and_old_write_hidden(new_client, clock):  # noqa: F811
    hr, pc, _ = await setup_basic(new_client)
    lid = (await late_punch(pc, clock))["letter_id"]
    assert (await hr.post(f"{L}/{lid}/auto/confirm", json={"explanation": REASON, "read": True})).status_code == 403
    d = (await pc.get(f"{L}/{lid}")).json()
    assert d["auto"] is True and d["can_write"] is False  # parolli eski forma avtomatik xatga ishlatilmaydi


async def test_disabled_and_threshold(new_client, clock):  # noqa: F811
    _, pc, _ = await setup_basic(new_client)
    async with SessionLocal() as s:
        v = await s.scalar(select(PenaltyRuleVersion).order_by(PenaltyRuleVersion.version.desc()))
        v.config = {**v.config, "auto_letters": False}
        await s.commit()
    body = await late_punch(pc, clock)
    assert body["letter_id"] is None
    async with SessionLocal() as s:
        assert await s.scalar(select(ExplanationLetter.id)) is None


async def test_scan_creates_letter_for_absence(new_client, clock):  # noqa: F811
    hr, pc, ctx = await setup_basic(new_client)
    clock.set("2026-11-04 10:00")
    async with SessionLocal() as s:
        rules = await current_rules(s)
        notes: list = []
        await scan_day(s, date(2026, 11, 3), rules, dry_run=False, moment=clock(), notes=notes)
        await s.commit()
        letter = await s.scalar(select(ExplanationLetter).where(ExplanationLetter.employee_id == ctx["emp_id"]))
    assert letter and letter.auto and letter.incident_type == "absent" and notes
    assert "ishga kelmadim" in svc.incident_text(letter.facts)
    clock.set("2026-11-04 08:50")
    r = await pc.post(f"{API}/punch", json={"method": "gps", **NEAR})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "letter_pending"
