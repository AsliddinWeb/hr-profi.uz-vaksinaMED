import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import anyio
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

# Argon2id OWASP tavsiyasi (m=19 MiB, t=2, p=1): xavfsiz va login uchun kutubxona standartidan (64 MiB, t=3, p=4)
# ~3-5 barobar arzon — 1000 kishilik yuklamada xotira/CPU tugamasin. Eski xeshlar loginda avtomatik yangilanadi (needs_rehash).
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
# Mavjud bo'lmagan login uchun ham bir xil vaqt sarflash (login enumeration oldini olish)
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")

JWT_ALG = "HS256"
MIN_PASSWORD_LEN = 8

# 0/O, 1/l/I kabi chalkash belgilarsiz (vaqtinchalik parol qog'ozga yoziladi)
_TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# Argon2 (64 MB xotira, ~0.1 s CPU) so'rov ichida sinxron chaqirilsa butun event loop to'xtaydi: bitta login
# tekshirilayotganda shu jarayondagi BARCHA so'rovlar kutadi. Shuning uchun so'rov yo'lida faqat quyidagi async
# variantlar ishlatiladi: hisob alohida thread'da, bir vaqtda ko'pi bilan HASH_CONCURRENCY ta (xotira cheklovi).
HASH_CONCURRENCY = 4
_limiter: anyio.CapacityLimiter | None = None


def _hash_limiter() -> anyio.CapacityLimiter:
    global _limiter  # noqa: PLW0603
    if _limiter is None:
        _limiter = anyio.CapacityLimiter(HASH_CONCURRENCY)
    return _limiter


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    return await anyio.to_thread.run_sync(verify_password, password, password_hash, limiter=_hash_limiter())


async def hash_password_async(password: str) -> str:
    return await anyio.to_thread.run_sync(hash_password, password, limiter=_hash_limiter())


def validate_password_strength(password: str, login: str) -> str | None:
    """None = yaroqli, aks holda xato kodi."""
    if len(password) < MIN_PASSWORD_LEN:
        return "password_too_short"
    if password.lower() == login.lower():
        return "password_same_as_login"
    if password.isdigit() or password.isalpha():
        return "password_too_simple"
    return None


def generate_temp_password(length: int = 10) -> str:
    while True:
        pwd = "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(length))
        # kamida bitta harf va bitta raqam
        if any(c.isdigit() for c in pwd) and any(c.isalpha() for c in pwd):
            return pwd


def new_refresh_token(session_id: str) -> tuple[str, str]:
    """(to'liq token `sid.secret`, hash). Faqat hash DB ga yoziladi."""
    secret = secrets.token_urlsafe(32)
    return f"{session_id}.{secret}", hash_token(secret)


def hash_token(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create_access_token(user_id: int, session_id: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_ttl_minutes),
    }
    return jwt.encode(payload, s.secret_key, algorithm=JWT_ALG)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
