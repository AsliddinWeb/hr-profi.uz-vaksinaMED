"""Ruxsatlar (permissions) va rollar katalogi.

Ruxsat kaliti: `<resurs>.<amal>` (masalan `users.create`). Wildcard: `users.*`, hamma narsa uchun `*`.
Core va mijoz extension'lari `register_permission` bilan o'z ruxsatlarini qo'shadi.
Rollar DB da saqlanadi (mijoz o'zgartira oladi); bu yerdagi ro'yxat faqat boshlang'ich (seed).
"""

from dataclasses import dataclass, field

PERMISSIONS: dict[str, dict[str, str]] = {}  # key -> {"uz": ..., "ru": ...}


def register_permission(key: str, uz: str, ru: str | None = None) -> None:
    PERMISSIONS[key] = {"uz": uz, "ru": ru or uz}


def matches(granted: set[str] | frozenset[str], needed: str) -> bool:
    """`granted` ichida `needed` ga mos ruxsat (aniq yoki wildcard) bormi."""
    if "*" in granted or needed in granted:
        return True
    parts = needed.split(".")
    return any(".".join(parts[:i]) + ".*" in granted for i in range(1, len(parts)))


def covers(granted: set[str] | frozenset[str], other: set[str] | frozenset[str]) -> bool:
    """`granted` `other` dagi HAR BIR ruxsatni qamrab oladimi (privilege escalation tekshiruvi)."""
    for perm in other:
        if perm.endswith(".*") or perm == "*":
            # wildcard'ni faqat shu yoki kengroq wildcard qamraydi
            if "*" in granted:
                continue
            prefix = perm[:-2] if perm.endswith(".*") else ""
            parts = prefix.split(".")
            if not any(".".join(parts[:i]) + ".*" in granted for i in range(1, len(parts) + 1)):
                return False
        elif not matches(granted, perm):
            return False
    return True


@dataclass(frozen=True)
class RoleDef:
    key: str
    uz: str
    ru: str
    permissions: tuple[str, ...] = field(default_factory=tuple)


SUPERUSER_ROLE = "tasischi"

SYSTEM_ROLES: tuple[RoleDef, ...] = (
    RoleDef("tasischi", "Ta'sischi", "Учредитель", ("*",)),
    RoleDef(
        "direktor",
        "Direktor",
        "Директор",
        (
            "users.read",
            "roles.read",
            "audit.read",
            "org.read",
            "branches.read",
            "employees.read",
            "employees.export",
            "schedule.read",
            "attendance.read",
            "attendance.punch",
            "face.enroll",
            "answers.request",
            "answers.read",
            "letters.own",
            "letters.read",
            "penalties.own",
            "penalties.read",
            "tasks.own",
            "tasks.assign",
            "tasks.read",
        ),
    ),
    RoleDef(
        "hr_direktor",
        "HR Direktor",
        "HR директор",
        (
            "users.*",
            "roles.read",
            "roles.manage",
            "audit.read",
            "sessions.manage",
            "notifications.send",
            "org.*",
            "branches.*",
            "employees.*",
            "schedule.*",
            "attendance.*",
            "face.*",
            "answers.*",
            "letters.*",
            "penalties.*",
            "tasks.*",
            "reminders.*",
            "pharmacy.*",
        ),
    ),
    RoleDef(
        "hr_menejer",
        "HR menejer",
        "HR менеджер",
        (
            "users.read",
            "users.create",
            "users.update",
            "users.reset_password",
            "org.read",
            "branches.read",
            "employees.read",
            "employees.sensitive",
            "employees.create",
            "employees.update",
            "employees.transfer",
            "employees.dismiss",
            "employees.documents",
            "employees.export",
            "employees.import",
            "employees.accounts",
            "schedule.read",
            "schedule.edit",
            "attendance.read",
            "attendance.edit",
            "attendance.qr",
            "attendance.punch",
            "face.enroll",
            "face.read",
            "face.manage",
            "answers.request",
            "answers.read",
            "answers.decide",
            "answers.manage",
            "letters.own",
            "letters.issue",
            "letters.read",
            "letters.review",
            "letters.manage",
            "penalties.own",
            "penalties.read",
            "penalties.approve",
            "tasks.own",
            "tasks.assign",
            "tasks.read",
            "tasks.manage",
        ),
    ),
    RoleDef(
        "koordinator", "Koordinator", "Координатор",
        ("org.read", "branches.read", "employees.read", "schedule.read", "attendance.read", "attendance.punch", "face.enroll", "answers.request", "answers.decide", "letters.own", "letters.issue", "penalties.own", "tasks.own", "tasks.assign"),
    ),
    RoleDef("mudir", "Mudir", "Заведующий", ("attendance.punch", "face.enroll", "answers.request", "letters.own", "penalties.own", "tasks.own", "tasks.assign", "attendance.qr")),
    RoleDef("farmasevt", "Farmasevt", "Фармацевт", ("attendance.punch", "face.enroll", "answers.request", "letters.own", "penalties.own", "tasks.own",)),
    RoleDef("stajyor", "Stajyor", "Стажёр", ("attendance.punch", "face.enroll", "answers.request", "letters.own", "penalties.own", "tasks.own",)),
    RoleDef("omborxona", "Omborxona xodimi", "Сотрудник склада", ("attendance.punch", "face.enroll", "answers.request", "letters.own", "penalties.own", "tasks.own",)),
    RoleDef("haydovchi", "Haydovchi", "Водитель", ("attendance.punch", "face.enroll", "answers.request", "letters.own", "penalties.own", "tasks.own",)),
    RoleDef("logistik", "Logistika menejeri", "Менеджер логистики", ("attendance.punch", "face.enroll", "answers.request", "letters.own", "penalties.own", "tasks.own", "employees.read", "branches.read", "tasks.assign")),
    RoleDef("resepshin", "Resepshin", "Ресепшн", ("attendance.punch", "face.enroll", "answers.request", "letters.own", "penalties.own", "tasks.own",)),
    RoleDef(
        "hr_auditor", "HR auditor", "HR-аудитор",
        ("employees.read", "branches.read", "attendance.read", "attendance.punch", "face.enroll", "answers.request", "recruit.read", "internship.read", "tasks.own", "tasks.read",
         "attestation.read", "performance.read", "retention.read", "retention.audit", "control.read", "letters.own", "penalties.own"),
    ),
    RoleDef("ayti", "AyTi", "ИТ", ("attendance.punch", "face.enroll", "answers.request", "letters.own", "penalties.own", "tasks.own",)),
)


def _with_reminders(roles: tuple[RoleDef, ...]) -> tuple[RoleDef, ...]:
    """Eslatmalar: hamma rol o'z eslatmalarini boshqaradi; topshiriq bera oladigan rollar boshqalarga ham yubora oladi."""
    out = []
    for r in roles:
        perms = list(r.permissions)
        have = frozenset(perms)
        if not matches(have, "reminders.own"):
            perms.append("reminders.own")
        if matches(have, "tasks.assign") and not matches(have, "reminders.assign"):
            perms.append("reminders.assign")
        out.append(RoleDef(r.key, r.uz, r.ru, tuple(perms)))
    return tuple(out)


SYSTEM_ROLES = _with_reminders(SYSTEM_ROLES)

_NEEDS_EXTRA = {
    "hr_direktor": ("needs.*",),
    "hr_menejer": ("needs.work", "needs.dispatch"),
    "direktor": ("needs.dispatch",),
    "ayti": ("needs.work",),
    "omborxona": ("needs.work",),
}
_DESK_EXTRA = {
    "hr_direktor": ("reception.*", "helpdesk.*", "calls.*", "ai.manage", "reports.*", "migration.manage"),
    "hr_menejer": ("reports.read", "calls.read", "calls.manage", "reception.desk", "reception.read", "helpdesk.work", "helpdesk.read", "helpdesk.manage"),
    "direktor": ("reception.read", "helpdesk.read", "calls.read", "reports.read"),
    "resepshin": ("reception.desk",),
    "ayti": ("helpdesk.work", "helpdesk.read"),
}
_MOBILE_EXTRA = {
    "hr_direktor": ("mobile.*",),
    "hr_menejer": ("mobile.read", "mobile.manage"),
    "direktor": ("mobile.read",),
}
_WAREHOUSE_EXTRA = {
    "hr_direktor": ("warehouse.*",),
    "hr_menejer": ("warehouse.read", "warehouse.manage"),
    "direktor": ("warehouse.read",),
    "logistik": ("warehouse.read",),
}
_LOGISTICS_EXTRA = {
    "hr_direktor": ("logistics.*",),
    "hr_menejer": ("logistics.read", "logistics.manage"),
    "direktor": ("logistics.read",),
    "haydovchi": ("logistics.own",),
    "logistik": ("logistics.*",),
}
_CANTEEN_EXTRA = {
    "hr_direktor": ("canteen.*",),
    "hr_menejer": ("canteen.read", "canteen.manage"),
    "direktor": ("canteen.read",),
}
_PAYROLL_EXTRA = {
    "hr_direktor": ("payroll.*",),
    "hr_menejer": ("payroll.read", "payroll.input"),
    "direktor": ("payroll.read",),
}
_INTERN_EXTRA = {
    "hr_direktor": ("internship.*",),
    "hr_menejer": ("internship.own", "internship.read", "internship.manage"),
    "direktor": ("internship.read",),
    "koordinator": ("internship.own",),
    "mudir": ("internship.own",),
    "stajyor": ("internship.own",),
}
_RECRUIT_EXTRA = {
    "hr_direktor": ("recruit.*",),
    "hr_menejer": ("recruit.read", "recruit.manage"),
    "direktor": ("recruit.read",),
}
_CHECKLIST_EXTRA = {
    "hr_direktor": ("checklists.*",),
    "hr_menejer": ("checklists.own", "checklists.read", "checklists.manage"),
    "direktor": ("checklists.read",),
    "koordinator": ("checklists.own",),
    "mudir": ("checklists.own",),
}
_PHARMACY_EXTRA = {
    "direktor": ("pharmacy.read",),
    "hr_menejer": ("pharmacy.read", "pharmacy.own", "pharmacy.request", "pharmacy.manage"),
    "koordinator": ("pharmacy.own", "pharmacy.request"),
    "mudir": ("pharmacy.own", "pharmacy.request"),
}
_EXT_EXTRA = {
    "hr_direktor": ("integrations.*", "complaints.*"),
    "hr_menejer": ("complaints.manage", "integrations.read"),
    "direktor": ("integrations.read",),
}
_RETENTION_EXTRA = {
    "hr_direktor": ("retention.*", "control.*"),
    "hr_menejer": ("retention.report", "retention.manage", "retention.read", "control.read"),
    "direktor": ("retention.read", "control.read"),
    "koordinator": ("retention.report",),
    "mudir": ("retention.report",),
}
_ROTATION_EXTRA = {
    "hr_direktor": ("rotations.*",),
    "hr_menejer": ("rotations.manage", "rotations.read", "rotations.request"),
    "direktor": ("rotations.read",),
    "hr_auditor": ("rotations.read",),
    "koordinator": ("rotations.request",),
    "mudir": ("rotations.request",),
}
_DUTY_EXTRA = {
    "hr_direktor": ("duty.*",),
    "hr_menejer": ("duty.manage", "duty.read", "duty.control"),
    "direktor": ("duty.read",),
    "hr_auditor": ("duty.read",),
    "koordinator": ("duty.control",),
    "mudir": ("duty.control",),
}
_HRDOCS_EXTRA = {
    "hr_direktor": ("hrdocs.*", "staffdocs.*"),
    "hr_menejer": ("hrdocs.manage", "staffdocs.manage", "staffdocs.read"),
    "direktor": ("staffdocs.read",),
    "hr_auditor": ("staffdocs.read",),
}
_GROWTH_EXTRA = {
    "hr_direktor": ("attestation.*", "performance.*", "career.*"),
    "hr_menejer": ("attestation.read", "attestation.manage", "performance.read", "performance.own", "career.read", "career.propose"),
    "direktor": ("attestation.read", "performance.read", "career.read"),
    "koordinator": ("performance.own", "career.propose"),
    "mudir": ("performance.own",),
}
SYSTEM_ROLES = tuple(
    RoleDef(
        r.key, r.uz, r.ru,
        tuple(dict.fromkeys((*r.permissions, *_PHARMACY_EXTRA.get(r.key, ()), *_GROWTH_EXTRA.get(r.key, ()), *_RETENTION_EXTRA.get(r.key, ()), *_ROTATION_EXTRA.get(r.key, ()), *_DUTY_EXTRA.get(r.key, ()), *_HRDOCS_EXTRA.get(r.key, ()), *_EXT_EXTRA.get(r.key, ()), *_NEEDS_EXTRA.get(r.key, ()), *_CHECKLIST_EXTRA.get(r.key, ()), *_RECRUIT_EXTRA.get(r.key, ()), *_INTERN_EXTRA.get(r.key, ()), *_PAYROLL_EXTRA.get(r.key, ()), *_CANTEEN_EXTRA.get(r.key, ()), *_LOGISTICS_EXTRA.get(r.key, ()), *_WAREHOUSE_EXTRA.get(r.key, ()), *_MOBILE_EXTRA.get(r.key, ()), *_DESK_EXTRA.get(r.key, ()), *(() if r.key == SUPERUSER_ROLE else ("attestation.own", "duty.own", "hrdocs.read", "staffdocs.apply", "complaints.own", "needs.own", "payroll.own", "canteen.own", "mobile.own", "reception.own", "helpdesk.own", "calls.own", "ai.use"))))),
    )
    for r in SYSTEM_ROLES
)
