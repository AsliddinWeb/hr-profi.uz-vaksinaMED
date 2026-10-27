"""Rekruting oqimi: tajriba darajasi -> ochiladigan bosqichlar, job offer, nomzodga Telegram xabari."""

from app.models.recruit import Application, Candidate, Vacancy
from app.services.notifications import register_template

# Suhbatdan keyin aniqlanadi (deck, 21-slayd): yuqori -> 3 bosqich, o'rta -> 2, tajribasiz -> faqat stajyor
STAGES_BY_LEVEL = {"high": ["intern", "pharmacist", "senior"], "mid": ["intern", "pharmacist"], "none": ["intern"]}
LEVEL_UZ = {"intern": "Stajyor", "pharmacist": "Farmatsevt", "senior": "Katta farmatsevt"}

register_template(
    "recruit.offer_review",
    {"uz": "Job offer tasdiqlanishi kerak", "ru": "Нужно утвердить job offer"},
    {"uz": "{candidate}: {level}, {salary} so'm", "ru": "{candidate}: {level}, {salary} сум"},
    "info",
)
register_template(
    "recruit.offer_decided",
    {"uz": "Job offer bo'yicha qaror", "ru": "Решение по job offer"},
    {"uz": "{candidate}: {result}. {note}", "ru": "{candidate}: {result}. {note}"},
    "info",
)


def money(n: int | None) -> str:
    return f"{n:,}".replace(",", " ") if n else "—"


def invite_text(v: Vacancy, when_text: str, place: str | None) -> str:
    lines = [f"👋 Salom! «{v.title}» vakansiyasi bo'yicha suhbatga taklif qilamiz.", f"🕘 Vaqt: {when_text}"]
    if place:
        lines.append(f"📍 Joy: {place}")
    lines.append("Iltimos, vaqtida keling. Savol bo'lsa shu yerga yozing.")
    return "\n".join(lines)


def offer_text(a: Application, v: Vacancy | None) -> str:
    lines = [f"🎉 Tabriklaymiz! «{v.title if v else ''}» bo'yicha job offer:", f"💼 Lavozim darajasi: {LEVEL_UZ.get(a.offer_level or '', '—')}", f"💰 Oylik (fiks): {money(a.offer_salary)} so'm"]
    if a.offer_start:
        lines.append(f"📅 Ishga chiqish: {a.offer_start:%d.%m.%Y}")
    if a.offer_note:
        lines.append(a.offer_note)
    lines.append("Rozi bo'lsangiz, shu yerga yozing — HR siz bilan bog'lanadi.")
    return "\n".join(lines)


def check_level(a: Application, level: str) -> None:
    from app.deps import error  # noqa: PLC0415

    if a.experience_level is None:
        raise error(409, "interview_required")
    if level not in STAGES_BY_LEVEL[a.experience_level]:
        raise error(400, "level_not_unlocked")
    if a.bg_status == "failed":
        raise error(409, "background_failed")


def can_message(c: Candidate | None) -> bool:
    return bool(c and c.telegram_chat_id)

