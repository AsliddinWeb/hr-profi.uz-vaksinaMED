"""Yuk testi uchun sun'iy ma'lumot (FAQAT alohida test bazasida: `ALLOW_SEED_LOAD=1`). Haqiqiy mijoz bazasiga ishlatilmaydi."""

import os
import random
from datetime import date, datetime, timedelta

from sqlalchemy import insert, select

from app.db import SessionLocal
from app.models.attendance import AttendanceRecord
from app.models.auth import Role, User
from app.models.employees import Employee
from app.models.helpdesk import Ticket
from app.models.org import Branch, Department, Position
from app.models.tasks import Task
from app.security import hash_password
from app.services.seed import ensure_roles
from app.timeutil import tz

PASSWORD = "Load-test-1234"
FIRST = ["Aziz", "Dilnoza", "Bobur", "Malika", "Jasur", "Nodira", "Sherzod", "Madina", "Otabek", "Zilola"]
LAST = ["Karimov", "Aliyeva", "Rustamov", "Soliyeva", "Yusupov", "Ergasheva", "Tursunov", "Nazarova", "Umarov", "Saidova"]


async def seed(employees: int, users: int, days: int = 30) -> dict[str, int]:
    if os.environ.get("ALLOW_SEED_LOAD") != "1":
        raise SystemExit("ALLOW_SEED_LOAD=1 kerak (faqat alohida test bazasi uchun)")
    rnd = random.Random(7)
    async with SessionLocal() as s:
        await ensure_roles(s)
        if await s.scalar(select(Employee.id).limit(1)):
            raise SystemExit("Baza bo'sh emas")
        depts = [Department(name=f"Bo'lim {i}", kind="office") for i in range(8)]
        s.add_all(depts)
        await s.flush()
        s.add_all(Position(name=f"Lavozim {i}", department_id=depts[i % 8].id) for i in range(16))
        branches = [Branch(number=i + 1, name=f"Filial {i + 1}", department_id=depts[0].id) for i in range(40)]
        s.add_all(branches)
        await s.flush()
        poss = list((await s.scalars(select(Position))).all())
        emps = []
        for i in range(employees):
            ln, fn = rnd.choice(LAST), rnd.choice(FIRST)
            emps.append(Employee(last_name=ln, first_name=fn, full_name=f"{ln} {fn} {i}", phone=f"+998{rnd.randrange(10**8, 10**9)}", department_id=rnd.choice(depts).id,
                                 position_id=rnd.choice(poss).id, branch_id=rnd.choice(branches).id, hire_date=date(2024, 1, 1), status="active"))  # fmt: skip
        s.add_all(emps)
        await s.flush()
        roles = {r.key: r.id for r in (await s.scalars(select(Role))).all()}
        pw = hash_password(PASSWORD)
        hr_users = [User(login=f"hr{i}", password_hash=pw, full_name=f"HR {i}", role_id=roles["hr_direktor"], must_change_password=False) for i in range(5)]
        staff = [User(login=f"u{i}", password_hash=pw, full_name=f"Xodim {i}", role_id=roles["farmasevt"], must_change_password=False) for i in range(users)]
        s.add_all(hr_users + staff)
        await s.flush()
        for u, e in zip(staff, emps, strict=False):
            e.user_id = u.id
        today = date.today()
        rows = []
        for e in emps:
            for d in range(1, days + 1):
                wd = today - timedelta(days=d)
                if wd.weekday() == 6 or rnd.random() < 0.1:
                    continue
                cin = datetime(wd.year, wd.month, wd.day, 9, rnd.randrange(0, 25), tzinfo=tz())
                rows.append({"employee_id": e.id, "work_date": wd, "check_in_at": cin, "check_out_at": cin + timedelta(hours=9), "in_method": "qr", "out_method": "qr", "branch_id": e.branch_id,
                             "late_minutes": max(0, cin.minute - 5), "worked_minutes": 540, "is_manual": False, "track_lateness": True, "early_leave_minutes": 0})  # fmt: skip
        for i in range(0, len(rows), 5000):
            await s.execute(insert(AttendanceRecord), rows[i : i + 5000])
        s.add_all(Task(title=f"Topshiriq {i}", creator_id=hr_users[i % 5].id, assignee_id=staff[i % users].id, status=rnd.choice(["todo", "in_progress", "done"]), priority="normal") for i in range(600))
        await s.flush()
        t_rows = [
            {"number": f"T-L-{i:05d}", "title": f"Ticket {i}", "status": "new", "priority": "normal", "requester_id": staff[i % users].id, "opened_at": datetime.now(tz()), "reopen_count": 0, "sla_breached": False}
            for i in range(300)
        ]
        await s.execute(insert(Ticket), t_rows)
        await s.commit()
        return {"employees": employees, "users": users + 5, "attendance": len(rows), "tasks": 600, "tickets": 300}
