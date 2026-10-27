"""Bildirishnomalar: shablonlar, yaratish (`notify`) va yetkazish (`deliver`).

Ishlatish (route ichida):
    notes = await notify(db, [user.id], "security.password_changed")
    await db.commit()
    await deliver(request.app, notes)      # realtime + Telegram (commitdan KEYIN)

Mijoz extension o'z shablonlarini `register_template(...)` bilan qo'shadi.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from app.config import get_settings
from app.models.notifications import Notification
from app.realtime import publish

log = logging.getLogger("vaksina.notify")

SEVERITIES = {"info", "success", "warning", "danger"}


@dataclass(frozen=True)
class Template:
    severity: str
    title: dict[str, str]
    body: dict[str, str] | None = None


TEMPLATES: dict[str, Template] = {}


def register_template(
    kind: str,
    title: dict[str, str],
    body: dict[str, str] | None = None,
    severity: str = "info",
) -> None:
    TEMPLATES[kind] = Template(severity, title, body)


register_template(
    "security.password_changed",
    {"uz": "Parolingiz o'zgartirildi", "ru": "Ваш пароль изменён"},
    {
        "uz": "Agar buni siz qilmagan bo'lsangiz, darhol HR bilan bog'laning.",
        "ru": "Если это были не вы, немедленно свяжитесь с HR.",
    },
    "warning",
)
register_template(
    "account.role_changed",
    {"uz": "Rolingiz o'zgartirildi", "ru": "Ваша роль изменена"},
    {"uz": "Yangi rol: {role_uz}", "ru": "Новая роль: {role_ru}"},
)
register_template(
    "org.head_assigned",
    {"uz": "Siz bo'lim boshlig'i etib tayinlandingiz", "ru": "Вас назначили руководителем отдела"},
    {"uz": "Bo'lim: {name}", "ru": "Отдел: {name}"},
    "success",
)
register_template(
    "branch.manager_assigned",
    {"uz": "Siz filial mudiri etib tayinlandingiz", "ru": "Вас назначили заведующим филиала"},
    {"uz": "Filial: {name}", "ru": "Филиал: {name}"},
    "success",
)
register_template(
    "branch.coordinator_assigned",
    {"uz": "Sizga filial biriktirildi", "ru": "За вами закреплён филиал"},
    {"uz": "Filial: {name}", "ru": "Филиал: {name}"},
    "info",
)
register_template(
    "employee.transferred",
    {"uz": "Ish joyingiz o'zgartirildi", "ru": "Ваше место работы изменено"},
    {"uz": "{summary}", "ru": "{summary}"},
)
register_template(
    "telegram.linked",
    {"uz": "Telegram ulandi", "ru": "Telegram подключён"},
    {
        "uz": "Endi bildirishnomalar Telegramga ham keladi.",
        "ru": "Теперь уведомления будут приходить и в Telegram.",
    },
    "success",
)


def _fmt(
    texts: dict[str, str] | None, lang: str, params: dict[str, Any], literal: bool = False
) -> str | None:
    """Shablonni to'ldiradi. `literal=True`: matn foydalanuvchi kiritgan, formatlanmaydi."""
    if texts is None:
        return None
    text = texts.get(lang) or texts.get("uz") or ""
    if literal:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        log.warning("Shablon to'ldirilmadi: %s", text)
        return text


async def notify(
    session,
    user_ids: Iterable[int],
    kind: str,
    *,
    params: dict[str, Any] | None = None,
    link: str | None = None,
    severity: str | None = None,
    title: dict[str, str] | None = None,
    body: dict[str, str] | None = None,
) -> list[Notification]:
    """Bildirishnoma qatorlarini JORIY tranzaksiyaga qo'shadi (yetkazish `deliver` da, commitdan keyin).

    `title`/`body` berilsa shablon o'rniga ishlatiladi (masalan, qo'lda yuborilgan xabar).
    """
    tpl = TEMPLATES.get(kind)
    if tpl is None and title is None:
        raise KeyError(f"Bildirishnoma shabloni yo'q: {kind}")
    params = params or {}
    sev = severity or (tpl.severity if tpl else "info")
    if sev not in SEVERITIES:
        sev = "info"
    title_src = title or (tpl.title if tpl else {})
    body_src = body if body is not None else (tpl.body if tpl else None)

    created: list[Notification] = []
    for uid in dict.fromkeys(user_ids):
        n = Notification(
            user_id=uid,
            kind=kind,
            severity=sev,
            title_uz=(_fmt(title_src, "uz", params, title is not None) or "")[:200],
            title_ru=(_fmt(title_src, "ru", params, title is not None) or "")[:200],
            body_uz=_fmt(body_src, "uz", params, body is not None),
            body_ru=_fmt(body_src, "ru", params, body is not None),
            link=link,
            data=params or None,
        )
        session.add(n)
        created.append(n)
    await session.flush()
    return created


def serialize(n: Notification) -> dict[str, Any]:
    return {
        "id": n.id,
        "kind": n.kind,
        "severity": n.severity,
        "title": {"uz": n.title_uz, "ru": n.title_ru},
        "body": {"uz": n.body_uz, "ru": n.body_ru},
        "link": n.link,
        "created_at": n.created_at,
        "read": n.read_at is not None,
    }


async def deliver(app: FastAPI, notifications: list[Notification], *, telegram: bool = True) -> None:
    """Realtime (WebSocket) va Telegram navbatiga yuboradi. Xato asosiy amalni buzmasligi kerak."""
    if not notifications:
        return
    settings = get_settings()
    try:
        for n in notifications:
            await publish(app.state.redis, [n.user_id], "notification", {"notification": serialize(n)})
        if telegram and settings.telegram_bot_token:
            for n in notifications:
                await app.state.queue.enqueue("deliver_telegram", n.id)
    except Exception:  # noqa: BLE001
        log.exception("Bildirishnomani yetkazishda xato (amal saqlangan)")
