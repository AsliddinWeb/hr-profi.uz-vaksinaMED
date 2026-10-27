"""Namoyish (demo) ma'lumotlari: tizimni mijozga ko'rsatish uchun barcha bo'limlarni ketma-ket to'ldiradi.

`ALLOW_DEMO_SEED=1 python -m app.cli seed-demo-all` — AVVAL barcha ish ma'lumotlarini o'chiradi (faqat Ta'sischi
hisoblari, rollar va sozlamalar qoladi), so'ng REST API orqali (haqiqiy biznes qoidalari bilan) namunaviy yozuvlarni yaratadi.
Telegram/worker ishlamaydi (navbat soxta), tashqi tomonga hech narsa yuborilmaydi.
HAQIQIY ish ma'lumoti bor bazada ISHLATMANG.
"""

import logging
import os
import random
from datetime import date, datetime, timedelta

import httpx
from redis.asyncio import Redis
from sqlalchemy import insert, select, text

from app.config import get_settings
from app.db import SessionLocal
from app.main import create_app
from app.models.attendance import AttendanceRecord
from app.models.auth import Role, User
from app.models.employees import Employee
from app.security import hash_password
from app.services.seed import ensure_roles
from app.timeutil import tz

logging.getLogger("httpx").setLevel(logging.WARNING)
DEMO_PASSWORD = "Demo-2026!"
KEEP = {"alembic_version", "app_meta", "roles", "role_permissions", "users", "ai_settings", "canteen_settings", "penalty_rule_versions"}
H = {"X-Requested-With": "demo"}

# (familiya, ism, rol, bo'lim, lavozim, filial raqami yoki None, telefon oxiri)
STAFF = [
    ("Karimov", "Jasur", "direktor", "Rahbariyat", "Direktor", None, "01"),
    ("Aliyeva", "Dilnoza", "hr_direktor", "HR bo'limi", "HR direktor", None, "02"),
    ("Rustamova", "Malika", "hr_menejer", "HR bo'limi", "HR menejer", None, "03"),
    ("Yusupov", "Bobur", "koordinator", "Dorixona tarmog'i", "Koordinator", None, "04"),
    ("Ergashev", "Sherzod", "mudir", "Dorixona tarmog'i", "Mudir", 16, "05"),
    ("Nazarova", "Madina", "mudir", "Dorixona tarmog'i", "Mudir", 36, "06"),
    ("Soliyeva", "Nodira", "farmasevt", "Dorixona tarmog'i", "Farmasevt", 16, "07"),
    ("Tursunov", "Otabek", "farmasevt", "Dorixona tarmog'i", "Farmasevt", 16, "08"),
    ("Umarova", "Zilola", "farmasevt", "Dorixona tarmog'i", "Farmasevt", 36, "09"),
    ("Saidov", "Aziz", "farmasevt", "Dorixona tarmog'i", "Farmasevt", 11, "10"),
    ("Qodirova", "Shahlo", "farmasevt", "Dorixona tarmog'i", "Farmasevt", 6, "11"),
    ("Hamidov", "Doniyor", "farmasevt", "Dorixona tarmog'i", "Farmasevt", 67, "12"),
    ("Ismoilova", "Laylo", "stajyor", "Dorixona tarmog'i", "Stajyor", 11, "13"),
    ("Abdullayev", "Rustam", "stajyor", "Dorixona tarmog'i", "Stajyor", 16, "14"),
    ("Mirzayev", "Anvar", "omborxona", "Omborxona", "Omborchi", None, "15"),
    ("Xolmatov", "Sardor", "haydovchi", "Logistika", "Haydovchi", None, "16"),
    ("Normatova", "Gulnora", "logistik", "Logistika", "Logistika menejeri", None, "17"),
    ("Orifov", "Behruz", "ayti", "AyTi", "AyTi mutaxassisi", None, "18"),
    ("Jo'rayeva", "Sevara", "resepshin", "Rahbariyat", "Resepshin", None, "19"),
    ("Nurmatov", "Eldor", "hr_auditor", "Reviziya", "Auditor", None, "20"),
]
LOGIN_OF: dict[str, str] = {}  # "Familiya Ism" -> login


class Seeder:
    def __init__(self) -> None:
        self.app = create_app()
        self.clients: dict[str, httpx.AsyncClient] = {}
        self.ids: dict[str, dict] = {}
        self.ok = 0
        self.fail = 0
        self.rnd = random.Random(11)

    # ---- yordamchilar
    def _mk(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://demo", headers=H, timeout=60)

    async def login(self, login: str, password: str = DEMO_PASSWORD) -> httpx.AsyncClient:
        if login in self.clients:
            return self.clients[login]
        c = self._mk()
        r = await c.post("/api/auth/login", json={"login": login, "password": password})
        if r.status_code != 200:
            raise RuntimeError(f"login {login}: {r.status_code} {r.text[:120]}")
        self.clients[login] = c
        return c

    async def call(self, who: str, method: str, url: str, label: str = "", **kw):
        """Bitta so'rov: muvaffaqiyat/xatoni sanaydi, xatoda to'xtamaydi."""
        c = await self.login(who)
        r = await c.request(method, url, **kw)
        if r.status_code >= 400:
            self.fail += 1
            print(f"  ✗ {label or url}: {r.status_code} {r.text[:160]}")
            return None
        self.ok += 1
        try:
            return r.json()
        except ValueError:
            return None

    def login_of(self, last: str) -> str:
        return next(v for k, v in LOGIN_OF.items() if k.startswith(last))

    # ---- 0. tozalash
    async def wipe(self) -> None:
        async with SessionLocal() as s:
            names = [r[0] for r in await s.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))]
            drop = [n for n in names if n not in KEEP]
            await s.execute(text("TRUNCATE " + ", ".join(f'"{n}"' for n in drop) + " RESTART IDENTITY"))
            sup = await s.scalar(select(Role.id).where(Role.key == "tasischi"))
            await s.execute(text("DELETE FROM users WHERE role_id <> :r OR login = 'demo_seeder'"), {"r": sup})
            await s.commit()
            for seq in ("need_no_seq", "ticket_no_seq"):
                try:
                    await s.execute(text(f"ALTER SEQUENCE {seq} RESTART"))
                except Exception:  # noqa: BLE001
                    await s.rollback()
            await s.commit()
            await ensure_roles(s)
            from app.services.letters import ensure_default_template
            from app.services.penalties import ensure_default_rules

            await ensure_default_template(s)
            await ensure_default_rules(s)
        print(f"Tozalandi: {len(drop)} jadval")

    async def make_seeder_user(self) -> None:
        async with SessionLocal() as s:
            role = await s.scalar(select(Role).where(Role.key == "tasischi"))
            s.add(User(login="demo_seeder", password_hash=hash_password(DEMO_PASSWORD), full_name="Demo seeder", role_id=role.id, must_change_password=False))
            await s.commit()

    # ---- 1. tuzilma
    async def org(self) -> None:
        print("1. Tuzilma, smenalar, bayramlar")
        from app.cli import seed_demo_org, seed_demo_schedule

        print("  ", await seed_demo_org(), "|", await seed_demo_schedule())
        await self.call("demo_seeder", "POST", "/api/v1/schedule/holidays/seed", json={"year": date.today().year, "yearly": True}, label="bayramlar")
        d = await self.call("demo_seeder", "GET", "/api/v1/org/departments")
        br = await self.call("demo_seeder", "GET", "/api/v1/branches")
        dl = d if isinstance(d, list) else (d or {}).get("items", [])
        self.ids["dept"] = {x["name"]: x["id"] for x in dl}
        brl = br if isinstance(br, list) else (br or {}).get("items", [])
        self.ids["branch"] = {x["number"]: x["id"] for x in brl}
        self.ids["pos"] = {}
        for name, dept in [(p[4], p[3]) for p in STAFF] + [("Farmasevt", "Dorixona tarmog'i")]:
            key = (name, dept)
            if key in self.ids["pos"]:
                continue
            r = await self.call("demo_seeder", "POST", "/api/v1/org/positions", json={"name": name, "department_id": self.ids["dept"][dept]}, label=f"lavozim {name}")
            if r:
                self.ids["pos"][key] = r["id"]
        groups = await self.call("demo_seeder", "GET", "/api/v1/schedule/groups")
        gl = groups if isinstance(groups, list) else (groups or {}).get("items", [])
        self.ids["group"] = {g["category"]: g["id"] for g in gl}

    # ---- 2. xodimlar va hisoblar
    async def staff(self) -> None:
        print("2. Xodimlar va hisoblar")
        cat = {"Dorixona tarmog'i": "pharmacy", "Omborxona": "warehouse"}
        for last, first, role, dept, pos, bno, tail in STAFF:
            body = {
                "last_name": last, "first_name": first, "phone": f"+99890123{int(tail):04d}",
                "gender": "f" if first[-1] == "a" else "m",
                "birth_date": f"{self.rnd.randint(1985, 2002)}-0{self.rnd.randint(1, 9)}-1{self.rnd.randint(0, 9)}",
                "department_id": self.ids["dept"][dept], "position_id": self.ids["pos"].get((pos, dept)),
                "hire_date": str(date.today() - timedelta(days=self.rnd.randint(60, 900))),
                "create_account": True, "role_key": role,
            }
            if bno:
                body["branch_id"] = self.ids["branch"].get(bno)
            g = self.ids["group"].get(cat.get(dept, "office"))
            if g:
                body["work_group_id"] = g
            r = await self.call("demo_seeder", "POST", "/api/v1/employees", json=body, label=f"xodim {last}")
            if r and r.get("login"):
                LOGIN_OF[f"{last} {first}"] = r["login"]
        # barcha hisoblarga bir xil demo parol, majburiy almashtirishsiz
        async with SessionLocal() as s:
            await s.execute(text("UPDATE users SET password_hash=:h, must_change_password=false WHERE login <> 'demo_seeder' AND role_id <> (SELECT id FROM roles WHERE key='tasischi')"), {"h": hash_password(DEMO_PASSWORD)})
            await s.commit()
        print("  hisoblar:", len(LOGIN_OF))

    # ---- 3. davomat tarixi (to'g'ridan-to'g'ri, 21 kun)
    async def attendance_history(self) -> None:
        print("3. Davomat tarixi (21 kun)")
        async with SessionLocal() as s:
            emps = list((await s.scalars(select(Employee).where(Employee.status == "active"))).all())
            today = date.today()
            rows = []
            for e in emps:
                for d in range(1, 22):
                    wd = today - timedelta(days=d)
                    if wd.weekday() == 6 or self.rnd.random() < 0.07:
                        continue
                    late = self.rnd.choice([0, 0, 0, 0, 3, 12, 25, 40])
                    cin = datetime(wd.year, wd.month, wd.day, 9, 0, tzinfo=tz()) + timedelta(minutes=late)
                    out_h = 8 if late < 30 else 7
                    rows.append({"employee_id": e.id, "work_date": wd, "check_in_at": cin, "check_out_at": cin + timedelta(hours=out_h, minutes=self.rnd.randint(0, 20)),
                                 "in_method": self.rnd.choice(["face", "qr", "gps"]), "out_method": "qr", "branch_id": e.branch_id, "late_minutes": max(0, late - 10),
                                 "worked_minutes": out_h * 60, "is_manual": False, "track_lateness": True, "early_leave_minutes": 0})  # fmt: skip
            for i in range(0, len(rows), 2000):
                await s.execute(insert(AttendanceRecord), rows[i : i + 2000])
            await s.commit()
        print("  yozuvlar:", len(rows))

    async def run(self) -> None:
        if os.environ.get("ALLOW_DEMO_SEED") != "1":
            raise SystemExit("ALLOW_DEMO_SEED=1 kerak: bu buyruq barcha ish ma'lumotlarini O'CHIRADI")
        redis = Redis.from_url(get_settings().redis_url, decode_responses=True)

        class Q:
            async def enqueue(self, *a, **k):
                return None

        class St:
            async def put(self, *a, **k):
                return None

            async def delete(self, *a, **k):
                return None

            async def stream(self, key):
                if False:
                    yield b""

        self.app.state.redis, self.app.state.queue, self.app.state.storage = redis, Q(), St()
        await self.wipe()
        await self.make_seeder_user()
        await self.org()
        await self.staff()
        await self.attendance_history()
        from app.demoseed_flows import flows

        await flows(self)
        # vaqtinchalik seeder foydalanuvchisini o'chirish
        async with SessionLocal() as s:
            await s.execute(text("TRUNCATE audit_log, user_sessions"))
            await s.execute(text("DELETE FROM users WHERE login='demo_seeder'"))
            await s.commit()
        for c in self.clients.values():
            await c.aclose()
        await redis.aclose()
        print(f"\nTAYYOR: {self.ok} muvaffaqiyatli, {self.fail} xato. Barcha demo hisoblar paroli: {DEMO_PASSWORD}")
        for name, login in LOGIN_OF.items():
            print(f"  {login:22} {name}")


async def seed_demo_all() -> None:
    await Seeder().run()
