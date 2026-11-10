"""Nutqni matnga aylantirish (OpenAI Whisper) va ovoz chiqarib o'qish aniqligi.

Kalit (`OPENAI_API_KEY`) bo'lmasa `configured()` False — ovozli funksiyalar o'chiq, yozma javob ishlayveradi.
Audio faqat matnga aylantirish uchun yuboriladi; tashqi xizmatda saqlanmaydi (OpenAI API siyosati).
"""

import difflib
import re

import httpx

from app.config import get_settings
from app.deps import error

MAX_AUDIO_BYTES = 15 * 1024 * 1024
EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav"}


def configured() -> bool:
    return bool(get_settings().openai_api_key)


async def transcribe(data: bytes, mime: str, lang: str = "uz") -> str:
    """Audio -> matn. Xatolarda 503/502 qaytaradi (sabab foydalanuvchiga ko'rinadi, kalit hech qachon)."""
    s = get_settings()
    if not s.openai_api_key:
        raise error(503, "speech_disabled")
    if len(data) > MAX_AUDIO_BYTES:
        raise error(413, "audio_too_large")
    files = {"file": (f"audio.{EXT.get(mime, 'webm')}", data, mime)}
    form = {"model": s.whisper_model, "response_format": "json"}
    if lang in ("uz", "ru", "en"):
        form["language"] = lang
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{s.openai_base_url}/v1/audio/transcriptions", data=form, files=files, headers={"Authorization": f"Bearer {s.openai_api_key}"})
    except httpx.HTTPError:
        raise error(502, "speech_failed") from None
    if r.status_code >= 400:
        raise error(502, "speech_failed")
    return str((r.json() or {}).get("text") or "").strip()


_WORD = re.compile(r"[\w'ʻʼ‘’`-]+", re.U)


def _words(text: str) -> list[str]:
    norm = text.lower().replace("ʻ", "'").replace("ʼ", "'").replace("‘", "'").replace("’", "'").replace("`", "'")
    return [w.strip("-'") for w in _WORD.findall(norm) if w.strip("-'")]


def reading_score(expected: str, transcript: str) -> tuple[int, list[str]]:
    """O'qish aniqligi: kutilgan matn so'zlarining necha foizi to'g'ri tartibda o'qilgan (0-100) va o'qilmagan so'zlar."""
    exp, got = _words(expected), _words(transcript)
    if not exp:
        return 0, []
    sm = difflib.SequenceMatcher(a=exp, b=got, autojunk=False)
    matched = sum(b.size for b in sm.get_matching_blocks())
    missed: list[str] = []
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            missed.extend(exp[i1:i2])
    return round(matched / len(exp) * 100), list(dict.fromkeys(missed))[:30]
