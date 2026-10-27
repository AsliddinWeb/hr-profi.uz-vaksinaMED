"""`python -m app.cli create-admin [login] [full name]`: birinchi Ta'sischi foydalanuvchisini yaratadi.

Parol tasodifiy yaratiladi va FAQAT bir marta ekranga chiqadi. Birinchi kirishda almashtirish talab qilinadi.
"""

import asyncio
import sys

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models.auth import Role, User
from app.rbac import SUPERUSER_ROLE
from app.security import generate_temp_password, hash_password
from app.services.seed import ensure_roles


async def create_admin(login: str, full_name: str) -> str | None:
    async with SessionLocal() as session:
        await ensure_roles(session)
        if await session.scalar(select(User.id).where(User.login == login)):
            return None
        role = await session.scalar(select(Role).where(Role.key == SUPERUSER_ROLE))
        password = generate_temp_password(12)
        session.add(
            User(
                login=login,
                password_hash=hash_password(password),
                full_name=full_name,
                role_id=role.id,
                must_change_password=True,
            )
        )
        await session.commit()
        return password


DEMO_DEPARTMENTS = [  # (nom, ota, rang, turi)
    ("Rahbariyat", None, "#1e2a78", "office"),
    ("Ta'minot", "Rahbariyat", "#e8590c", "office"),
    ("Moliya", "Rahbariyat", "#12a150", "office"),
    ("HR bo'limi", "Rahbariyat", "#2563eb", "office"),
    ("AyTi", "Rahbariyat", "#0891b2", "office"),
    ("Xavfsizlik (SB)", "Rahbariyat", "#6b7280", "office"),
    ("Reviziya", "Rahbariyat", "#7c3aed", "office"),
    ("AXO va GPP", "Rahbariyat", "#db2777", "office"),
    ("Logistika", "Ta'minot", "#f59e0b", "office"),
    ("Omborxona", "Ta'minot", "#64748b", "warehouse"),
    ("Distribyutsiya", "Ta'minot", "#dc2626", "office"),
    ("Dorixona tarmog'i", "Rahbariyat", "#0d9488", "pharmacy"),
]
DEMO_BRANCHES = [  # (raqam, nom, tuman, lat, lng)
    (16, "1-gor bolnitsa", "Yunusobod", 41.3606, 69.2862),
    (36, "Ginekologiya-3", "Mirzo Ulug'bek", 41.3394, 69.3342),
    (11, "Yunusobod-15", "Yunusobod", 41.3702, 69.2918),
    (6, "Yunusobod-7", "Yunusobod", 41.3561, 69.2874),
    (67, "Yakkasaroy Bobur", "Yakkasaroy", 41.2896, 69.2677),
    (123, "Yangiobod korzinka", "Yangiobod", None, None),
]


async def seed_demo_org() -> str:
    """Faqat lokal sinov uchun: bo'sh bazaga namunaviy tuzilma (haqiqiy mijoz ma'lumoti emas)."""
    from app.models.org import Branch, Department, Position
    from app.services.org import DEFAULT_POSITIONS

    async with SessionLocal() as session:
        if await session.scalar(select(Department.id).limit(1)):
            return "Tuzilma bo'sh emas, o'tkazib yuborildi"
        by_name: dict[str, Department] = {}
        for i, (name, parent, color, kind) in enumerate(DEMO_DEPARTMENTS):
            d = Department(name=name, color=color, kind=kind, sort_order=i,
                           parent_id=by_name[parent].id if parent else None)  # fmt: skip
            session.add(d)
            await session.flush()
            by_name[name] = d
            for j, pn in enumerate(DEFAULT_POSITIONS):
                session.add(Position(name=pn, department_id=d.id, sort_order=j))
        net = by_name["Dorixona tarmog'i"]
        for number, name, district, lat, lng in DEMO_BRANCHES:
            session.add(Branch(number=number, name=name, district=district, latitude=lat,
                               longitude=lng, department_id=net.id))  # fmt: skip
        await session.commit()
        return f"Yaratildi: {len(DEMO_DEPARTMENTS)} bo'lim, {len(DEMO_BRANCHES)} filial"


async def seed_demo_schedule() -> str:
    """Faqat lokal sinov uchun: namunaviy smena/guruh/shablon (vaqtlar taxminiy, mijoz o'zgartiradi)."""
    from datetime import time

    from app.models.schedule import SchedulePattern, ShiftTemplate, WorkGroup

    async with SessionLocal() as session:
        if await session.scalar(select(ShiftTemplate.id).limit(1)):
            return "Smenalar bor, o'tkazib yuborildi"

        def shift(name, code, kind, start, end, brk, late, track, color, order):
            return ShiftTemplate(name=name, code=code, kind=kind, start_time=start, end_time=end,
                                 break_minutes=brk, late_grace_minutes=late, early_leave_grace_minutes=0,
                                 track_lateness=track, color=color, sort_order=order)  # fmt: skip

        office = shift("Ofis (namuna)", "OF", "fixed", time(9), time(18), 60, 10, True, "#2563eb", 1)
        s1 = shift("Dorixona 1-smena (namuna)", "D1", "fixed", time(8), time(15), 0, 10, True, "#16a34a", 2)
        s2 = shift("Dorixona 2-smena (namuna)", "D2", "fixed", time(15), time(22), 0, 10, True, "#d97706", 3)
        ombor = shift("Ombor erkin (namuna)", "OM", "flexible", time(8), time(7), 0, 0, False, "#9333ea", 4)
        sutka = shift("Sutkalik (namuna)", "S", "fixed", time(9), time(9), 0, 15, True, "#dc2626", 5)
        session.add_all([office, s1, s2, ombor, sutka])
        await session.flush()
        session.add_all([
            WorkGroup(name="Ofis", category="office", default_shift_id=office.id, weekly_off_days=[6],
                      observe_holidays=True, is_default=True, sort_order=1),
            WorkGroup(name="Dorixona", category="pharmacy", default_shift_id=s1.id, weekly_off_days=[],
                      observe_holidays=False, sort_order=2),
            WorkGroup(name="Omborxona", category="warehouse", default_shift_id=ombor.id, weekly_off_days=[6],
                      observe_holidays=True, sort_order=3),
            WorkGroup(name="Qo'riqlash", category="security", default_shift_id=sutka.id, weekly_off_days=[],
                      observe_holidays=False, sort_order=4),
            SchedulePattern(name="Dorixona 2/2", description="Ikki kun kunduzgi, ikki kun dam",
                            cycle=[{"shift_id": s1.id}, {"shift_id": s1.id}, {"shift_id": None}, {"shift_id": None}]),
            SchedulePattern(name="Sutka-uch", description="Sutkalik navbat, keyin 3 kun dam",
                            cycle=[{"shift_id": sutka.id}, {"shift_id": None}, {"shift_id": None}, {"shift_id": None}]),
        ])  # fmt: skip
        await session.commit()
        return "Yaratildi: 5 smena, 4 guruh, 2 shablon"


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "seed-demo-schedule":
        print(asyncio.run(seed_demo_schedule()))
        return 0
    if args and args[0] == "seed-demo-org":
        print(asyncio.run(seed_demo_org()))
        return 0
    if args and args[0] == "validate-client":
        from app.client_schema import validate_client_dir

        target = args[1] if len(args) > 1 else get_settings().client_dir
        errors, warnings = validate_client_dir(target)
        for w in warnings:
            print(f"ogohlantirish: {w}")
        for e in errors:
            print(f"XATO: {e}")
        print("client.yaml yaroqli" if not errors else f"{len(errors)} ta xato")
        return 1 if errors else 0
    if args and args[0] == "seed-load":
        from app.loadseed import seed

        n_emp = int(args[1]) if len(args) > 1 else 2000
        n_users = int(args[2]) if len(args) > 2 else 40
        print(asyncio.run(seed(n_emp, n_users)))
        return 0
    if args and args[0] == "client-schema":
        import json

        from app.client_schema import json_schema

        print(json.dumps(json_schema(), ensure_ascii=False, indent=2))
        return 0
    if not args or args[0] != "create-admin":
        print("Ishlatish: python -m app.cli create-admin [login] [To'liq ism] | seed-demo-org | seed-demo-schedule | validate-client [papka] | client-schema")
        return 1
    login = (args[1] if len(args) > 1 else "admin").lower()
    full_name = args[2] if len(args) > 2 else "Administrator"
    password = asyncio.run(create_admin(login, full_name))
    if password is None:
        print(f"Foydalanuvchi '{login}' allaqachon mavjud")
        return 1
    print(f"Yaratildi. Login: {login}\nVaqtinchalik parol: {password}\n(birinchi kirishda almashtiriladi)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
