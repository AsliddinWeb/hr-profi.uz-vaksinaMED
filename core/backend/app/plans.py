"""KOSHI tariflari: START / PRO / PREMIUM. Tarif modullarni belgilaydi, litsenziya foydalanuvchi sonini (o'rin) va muddatni cheklaydi.

Mijoz `client.yaml` da `plan: start|pro|premium` va `license: {seats, valid_until, holder}` beradi. `plan` berilmasa cheklov yo'q
(eski mijozlar o'zgarmaydi). Tarif tarkibi shu faylda: o'zgartirish uchun faqat `PLAN_MODULES` va `FEATURES` tahrirlanadi.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import error
from app.models.auth import User
from app.modules import CORE_MODULES

GRACE_DAYS = 14  # muddat tugagach shuncha kun faqat ogohlantirish, keyin yangi foydalanuvchi qo'shib bo'lmaydi

_START = ("dashboard", "org", "employees", "attendance", "answers", "discipline", "tasks", "reminders", "checklists", "internship", "reports")
_PRO = (*_START, "face_id", "calls", "logistics", "warehouse", "payroll", "mobile_tracking", "recruit", "recruitment", "needs", "pharmacy", "reception", "it_desk", "canteen")
_PREMIUM = (*_PRO, "ai", "migration")

PLAN_MODULES: dict[str, tuple[str, ...]] = {"start": _START, "pro": _PRO, "premium": _PREMIUM}
PLAN_ORDER = ("start", "pro", "premium")
PLAN_INFO: dict[str, dict[str, Any]] = {
    "start": {"name": "START", "price_usd": 3, "tagline": {"uz": "Kichik va o'sib borayotgan jamoalar uchun", "ru": "Для небольших и растущих команд"}},
    "pro": {"name": "PRO", "price_usd": 5, "tagline": {"uz": "Keng imkoniyatlar va yuqori samaradorlik", "ru": "Широкие возможности и высокая эффективность"}},
    "premium": {"name": "PREMIUM", "price_usd": 7, "tagline": {"uz": "Yirik kompaniyalar va tarmoqlar uchun", "ru": "Для крупных компаний и сетей"}},
}


@dataclass(frozen=True)
class Feature:
    key: str
    uz: str
    ru: str
    min_plan: str
    modules: tuple[str, ...] = ()
    built: bool = True  # False: hali ishlab chiqilmagan (yo'l xaritasi)


FEATURES: tuple[Feature, ...] = (
    Feature("attendance", "Davomat: QR va geohudud", "Посещаемость: QR и геозона", "start", ("attendance",)),
    Feature("tasks", "Vazifalar va checklist", "Задачи и чек-листы", "start", ("tasks", "checklists")),
    Feature("employees", "Xodimlar bazasi", "База сотрудников", "start", ("employees", "org")),
    Feature("schedule", "Smena va ish jadvali", "Смены и график", "start", ("attendance",)),
    Feature("reports", "Hisobotlar va dashboard", "Отчёты и дашборд", "start", ("reports", "dashboard")),
    Feature("hr_flow", "Preboarding / onboarding / offboarding", "Пребординг / онбординг / оффбординг", "start", ("internship",)),
    Feature("security", "Asosiy xavfsizlik va audit", "Базовая безопасность и аудит", "start"),
    Feature("face_id", "Face ID va qurilma nazorati", "Face ID и контроль устройств", "pro", ("face_id", "mobile_tracking")),
    Feature("fingerprint", "Barmoq izi integratsiyasi (qurilmaga bog'liq)", "Интеграция отпечатков пальцев (зависит от устройства)", "pro", (), False),
    Feature("conference", "Video/audio konferensiya", "Видео/аудио конференции", "pro", ("calls",)),
    Feature("logistics", "Logistika va transport nazorati", "Логистика и контроль транспорта", "pro", ("logistics", "warehouse")),
    Feature("finance", "Moliya va xarajatlar", "Финансы и расходы", "pro", ("payroll",), False),
    Feature("payroll", "KPI, bonus va ish haqi hisobi", "KPI, бонусы и расчёт зарплаты", "pro", ("payroll",)),
    Feature("custom_roles", "Kengaytirilgan analitika va rollar", "Расширенная аналитика и роли", "pro"),
    Feature("ai", "AI yordamida HR va hujjatlar", "HR и документы с помощью AI", "premium", ("ai",)),
    Feature("ai_agent", "AI Agent: vazifalarni avtomatik bajarish", "AI-агент: автоматическое выполнение задач", "premium", (), False),
    Feature("forecast", "Aqlli ogohlantirish va prognoz", "Умные оповещения и прогноз", "premium", (), False),
    Feature("workflows", "Avtomatik ish oqimlari", "Автоматические рабочие процессы", "premium", (), False),
    Feature("integrations", "API va korporativ integratsiyalar", "API и корпоративные интеграции", "premium", ("migration",)),
)
# /api/v1/<birinchi bo'lak> -> modul kaliti (backend darajasida o'chirilgan modulni yopish uchun)
PREFIX_MODULE: dict[str, str] = {
    "attendance": "attendance", "attendance-issues": "attendance", "coord-report": "attendance", "face": "face_id", "answers": "answers", "letters": "discipline", "penalties": "discipline",
    "tasks": "tasks", "reminders": "reminders", "employees": "employees", "org": "org", "branches": "org", "rotations": "org", "duty": "checklists", "hrdocs": "employees", "staffdocs": "employees", "recruit": "recruit", "internship": "internship", "kadr": "internship",
    "attestation": "internship", "growth": "internship", "retention": "internship", "offboarding": "internship", "control": "internship", "payroll": "payroll", "canteen": "canteen",
    "pharmacy": "pharmacy", "checklists": "checklists", "needs": "needs", "logistics": "logistics", "warehouse": "warehouse", "mobile": "mobile_tracking", "reception": "reception",
    "helpdesk": "it_desk", "calls": "calls", "ai": "ai", "migration": "migration", "reports": "reports", "integrations": "migration", "complaints": "employees",
}
FEATURE_BY_KEY = {f.key: f for f in FEATURES}

# Holat: mijozning joriy sozlamasi (process ichida bir marta o'rnatiladi)
_state: dict[str, Any] = {"plan": None, "license": {}}


def configure(plan: str | None, license_: dict[str, Any] | None) -> None:
    _state["plan"] = plan
    _state["license"] = dict(license_ or {})


def current_plan() -> str | None:
    return _state["plan"]


def plan_rank(plan: str) -> int:
    return PLAN_ORDER.index(plan)


def resolve_modules(plan: str | None, explicit: dict[str, Any] | None) -> dict[str, bool]:
    """client.yaml `modules` ni tarif bilan birlashtiradi: tarifdan tashqari modul yoqilmaydi, tarifdagini mijoz o'chira oladi."""
    explicit = explicit or {}
    mods = dict(CORE_MODULES)
    if plan in PLAN_MODULES:
        allowed = set(PLAN_MODULES[plan])
        for k in mods:
            mods[k] = k in allowed
    for k, v in explicit.items():
        if k not in CORE_MODULES:
            continue
        if plan in PLAN_MODULES and k not in PLAN_MODULES[plan] and v:
            continue  # tarifga kirmagan modulni yoqib bo'lmaydi
        mods[k] = bool(v)
    return mods


def feature_available(key: str, plan: str | None = None) -> bool:
    plan = plan if plan is not None else _state["plan"]
    f = FEATURE_BY_KEY.get(key)
    if f is None or plan is None:
        return True  # tarif belgilanmagan: cheklov yo'q
    return plan_rank(plan) >= plan_rank(f.min_plan)


def require_feature(key: str) -> None:
    if not feature_available(key):
        raise error(403, "plan_feature", feature=key, required=FEATURE_BY_KEY[key].min_plan)


def license_status(lic: dict[str, Any], today: date) -> str:
    """unlimited | active | grace | expired"""
    until = lic.get("valid_until")
    if not until:
        return "unlimited"
    if isinstance(until, str):
        until = date.fromisoformat(until)
    if today <= until:
        return "active"
    return "grace" if today <= until + timedelta(days=GRACE_DAYS) else "expired"


async def seats_used(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0


async def ensure_seat(db: AsyncSession, today: date | None = None, *, adding: int = 1) -> None:
    """Yangi faol foydalanuvchi qo'shishdan oldin: litsenziya muddati va o'rinlar soni tekshiriladi."""
    lic = _state["license"]
    if not lic:
        return
    from app.timeutil import local_date, now  # noqa: PLC0415

    st = license_status(lic, today or local_date(now()))
    if st == "expired":
        raise error(403, "license_expired")
    seats = lic.get("seats")
    if seats and await seats_used(db) + adding > int(seats):
        raise error(409, "seat_limit", seats=int(seats))


def compare_table(lang: str) -> list[dict[str, Any]]:
    return [{"key": f.key, "label": f.uz if lang == "uz" else f.ru, "min_plan": f.min_plan, "built": f.built} for f in FEATURES]
