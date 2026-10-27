import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g",
    "ҳ": "h",
}  # fmt: skip


def slugify(text: str) -> str:
    out = []
    for ch in text.lower():
        out.append(_CYR.get(ch, ch))
    s = "".join(out)
    s = re.sub(r"[ʻʼ'`’]", "", s)  # o'g'li -> ogli
    s = re.sub(r"[^a-z0-9]+", ".", s).strip(".")
    return s


def base_login(full_name: str) -> str:
    parts = [p for p in slugify(full_name).split(".") if p]
    return ".".join(parts[:2]) or "user"


async def unique_login(session: AsyncSession, full_name: str) -> str:
    base = base_login(full_name)[:56]
    candidate, n = base, 1
    while await session.scalar(select(User.id).where(User.login == candidate)):
        n += 1
        candidate = f"{base}{n}"
    return candidate
