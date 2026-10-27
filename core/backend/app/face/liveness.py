"""Faol liveness: tasodifiy ketma-ketlikda boshni burish (markaz -> chap/o'ng -> qarama-qarshi tomon).

Server har kadrda burilishni (yaw) landmarklardan hisoblaydi, ketma-ketlik va bitta shaxs ekanini tekshiradi.
Bu statik rasm va oddiy qog'oz/ekran ko'rsatishga qarshi; sertifikatlangan PAD (presentation attack detection) emas.
"""

import secrets

import numpy as np

from app.face.engine import FrameResult

CENTER_MAX = 0.15  # |yaw| shundan kichik: yuz to'g'ri qaragan
TURN_MIN = 0.30  # shundan katta: burilgan
SAME_PERSON_MIN = 0.30  # kadrlar orasidagi minimal kosinus (burilgan yuzda pasayadi)
MIN_VALID_FRAMES = 5
MAX_FRAMES = 12
CHALLENGE_TTL = 90


def new_steps() -> list[str]:
    first = secrets.choice(["left", "right"])
    return ["center", first, "right" if first == "left" else "left"]


def classify(yaw: float) -> str | None:
    if abs(yaw) <= CENTER_MAX:
        return "center"
    if yaw >= TURN_MIN:
        return "left"
    if yaw <= -TURN_MIN:
        return "right"
    return None


def verify_liveness(steps: list[str], frames: list[FrameResult]) -> tuple[bool, str | None]:
    """Kadrlar vaqt tartibida bo'lishi kerak. (ok, sabab)."""
    valid = [f for f in frames if f.ok and f.embedding is not None and f.yaw is not None]
    if len(valid) < MIN_VALID_FRAMES:
        return False, "not_enough_frames"
    # Bitta shaxs: hamma kadr birinchi markaziy kadrga yetarlicha o'xshash
    centers = [f for f in valid if classify(f.yaw or 0) == "center"]
    if not centers:
        return False, "no_center"
    ref = max(centers, key=lambda f: f.quality).embedding
    assert ref is not None
    for f in valid:
        if float(np.dot(ref, f.embedding)) < SAME_PERSON_MIN:  # type: ignore[arg-type]
            return False, "different_person"
    # Ketma-ketlik: qadamlar ketma-ket (tartib bo'yicha) uchraydi
    labels = [classify(f.yaw or 0) for f in valid]
    pos = 0
    for step in steps:
        try:
            pos = labels.index(step, pos) + 1
        except ValueError:
            return False, "challenge_failed"
    return True, None
