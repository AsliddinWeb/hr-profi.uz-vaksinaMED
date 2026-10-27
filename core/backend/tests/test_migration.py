from datetime import date

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.attendance import AttendanceRecord
from app.models.employees import Employee
from app.models.migration import MigrationLegacyId
from app.models.org import Branch, Department, Position
from app.services import migration as svc
from tests.conftest import login, make_user

pytestmark = pytest.mark.skipif(
    "not __import__('os').environ.get('DATABASE_URL')", reason="DATABASE_URL kerak"
)

M = "/api/v1/migration"

EMP_CSV = (
    "ID;F.I.SH;Telefon;Tug'ilgan sana;Bo'lim;Lavozim;Filial;Ishga olingan sana;Bo'shatilgan sana\n"
    "101;Karimov Aziz Bahodirovich;+998901112233;14.03.1998;Moliya;Hisobchi;16;01.02.2020;\n"
    "102;Aliyeva Dilnoza Karim qizi;+998902223344;02.07.1995;Moliya;Hisobchi;16;15.03.2021;30.06.2024\n"
    "103;Rustamov Bobur;+998903334455;;Ombor;Omborchi;№7;10.01.2022;\n"
    ";;;;;;;;\n"
    "104;;+998904445566;;Moliya;Hisobchi;16;01.01.2022;\n"
    "105;Soliyev Jasur;+99890bad;;Moliya;Hisobchi;16;01.01.2022;\n"
)

ATT_CSV = (
    "Xodim ID;Sana;Keldi;Ketdi;Kechikish\n"
    "101;01.10.2026;08:55;18:05;0\n"
    "101;02.10.2026;09:20;18:00;20\n"
    "102;01.10.2026;22:00;06:00;0\n"
    "101;01.10.2026;09:00;18:00;0\n"
    "999;01.10.2026;09:00;18:00;0\n"
    "101;03.10.2026;25:99;18:00;0\n"
    "101;04.10.2026;04.10.2026 09:00;06.10.2026 09:00;0\n"
    "103;05.10.2026;09:00;;0\n"
)


async def as_user(new_client, name, role):
    uid = await make_user(name, role)
    c = new_client()
    assert (await login(c, name)).status_code == 200
    return c, uid


async def upload(c, dataset, text, name="data.csv"):
    r = await c.post(f"{M}/batches", files={"file": (name, text.encode(), "text/csv")}, data={"dataset": dataset})
    assert r.status_code == 201, r.text
    return r.json()


async def count(model, *where):
    async with SessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(model).where(*where)) or 0


async def seed_org():
    async with SessionLocal() as db:
        d = Department(name="Moliya", kind="office")
        db.add(d)
        await db.flush()
        db.add(Position(name="Hisobchi", department_id=d.id))
        db.add(Branch(name="Yunusobod-15", number=16))
        await db.commit()


def test_parse_moment_variants():
    base = date(2026, 10, 1)
    assert svc.parse_moment("08:55", base)[0].hour == 8 and svc.parse_moment("08:55", base)[1] is True
    assert svc.parse_moment("02.10.2026 09:30", base)[0].day == 2 and svc.parse_moment("02.10.2026 09:30", base)[1] is False
    assert svc.parse_moment(0.5, base)[0].hour == 12
    assert svc.parse_moment("", base) == (None, False)
    for bad in ("25:00", "abc", "9"):
        with pytest.raises(ValueError):
            svc.parse_moment(bad, base)


async def test_permissions_and_file_validation(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    ali, _ = await as_user(new_client, "ali", "farmasevt")
    assert (await ali.get(f"{M}/batches")).status_code == 403
    r = await ali.post(f"{M}/batches", files={"file": ("a.csv", b"x", "text/csv")}, data={"dataset": "employees"})
    assert r.status_code == 403
    r = await hr.post(f"{M}/batches", files={"file": ("a.pdf", b"x", "application/pdf")}, data={"dataset": "employees"})
    assert r.status_code == 415
    r = await hr.post(f"{M}/batches", files={"file": ("a.csv", b"only header\n", "text/csv")}, data={"dataset": "employees"})
    assert r.json()["detail"]["code"] == "file_empty"
    r = await hr.post(f"{M}/batches", files={"file": ("a.csv", b"a;b\n1;2\n", "text/csv")}, data={"dataset": "nope"})
    assert r.json()["detail"]["code"] == "unknown_dataset"


async def test_employees_dry_run_apply_dedupe_and_rollback(new_client):
    hr, hr_id = await as_user(new_client, "hr", "hr_direktor")
    await seed_org()
    b = await upload(hr, "employees", EMP_CSV)
    assert b["status"] == "draft" and b["suggested"]["legacy_id"] == "ID" and b["suggested"]["full_name"] == "F.I.SH" and len(b["sample"]) == 5
    # moslashtirishsiz/noto'g'ri
    assert (await hr.put(f"{M}/batches/{b['id']}/mapping", json={"mapping": {"legacy_id": "Yo'q"}})).json()["detail"]["code"] == "unknown_column"
    assert (await hr.put(f"{M}/batches/{b['id']}/mapping", json={"mapping": {"legacy_id": "ID"}})).json()["detail"]["code"] == "mapping_required"

    # dry-run: Ombor bo'limi yo'q -> xato; hech narsa yozilmaydi
    r = await hr.put(f"{M}/batches/{b['id']}/mapping", json={"mapping": b["suggested"]})
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert r.json()["status"] == "previewed" and s["rows"] == 5 and s["created"] == 2 and s["errors"] == 3
    codes = {i["row"]: i["code"] for i in (await hr.get(f"{M}/batches/{b['id']}/issues")).json()["items"]}
    assert codes[4] == "department_unknown" and codes[5] == "name_required" and codes[6] == "phone_invalid"
    assert await count(Employee) == 0 and await count(MigrationLegacyId) == 0
    csv_out = await hr.get(f"{M}/batches/{b['id']}/issues.csv")
    assert csv_out.status_code == 200 and "department_unknown" in csv_out.text

    # yo'q ma'lumotnomalarni yaratish bilan: Ombor/Omborchi/№7
    r = await hr.put(f"{M}/batches/{b['id']}/mapping", json={"mapping": b["suggested"], "options": {"create_missing": True}})
    s = r.json()["summary"]
    assert s["created"] == 3 and s["errors"] == 2 and s["new_refs"] == {"departments": 1, "positions": 1, "branches": 1}
    assert await count(Employee) == 0 and await count(Department) == 1  # dry-run: ma'lumotnoma ham yaratilmadi

    r = await hr.post(f"{M}/batches/{b['id']}/apply")
    assert r.status_code == 200 and r.json()["status"] == "applied" and r.json()["summary"]["created"] == 3
    assert await count(Employee) == 3 and await count(Department) == 2 and await count(Branch) == 2
    assert await count(MigrationLegacyId) == 3
    async with SessionLocal() as db:
        emps = {e.last_name: e for e in (await db.scalars(select(Employee))).all()}
    assert emps["Aliyeva"].status == "dismissed" and emps["Aliyeva"].dismissal_date == date(2024, 6, 30) and emps["Karimov"].status == "active"
    assert emps["Karimov"].import_batch_id == b["id"] and emps["Karimov"].employee_no
    # qayta qo'llab bo'lmaydi
    assert (await hr.post(f"{M}/batches/{b['id']}/apply")).status_code == 409

    # xuddi shu fayl: eski ID lar -> o'tkazib yuboriladi
    b2 = await upload(hr, "employees", EMP_CSV)
    r = await hr.put(f"{M}/batches/{b2['id']}/mapping", json={"mapping": b2["suggested"], "options": {"create_missing": True}})
    assert r.json()["summary"]["created"] == 0
    issues = (await hr.get(f"{M}/batches/{b2['id']}/issues")).json()["items"]
    assert sum(1 for i in issues if i["code"] == "legacy_exists") == 3

    # orqaga qaytarish
    r = await hr.post(f"{M}/batches/{b['id']}/rollback")
    assert r.status_code == 200 and r.json()["status"] == "rolled_back" and r.json()["summary"]["rolled_back"]["employees"] == 3
    assert await count(Employee) == 0 and await count(MigrationLegacyId) == 0
    assert r.json()["summary"]["rolled_back"]["references"] == 3 and await count(Department) == 1 and await count(Branch) == 1  # yaratilgan ma'lumotnomalar ham qaytdi
    assert (await hr.post(f"{M}/batches/{b['id']}/rollback")).status_code == 409
    assert (await hr.delete(f"{M}/batches/{b['id']}")).status_code == 204


async def test_existing_person_is_linked_by_legacy_id(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    await seed_org()
    r = await hr.post("/api/v1/employees", json={"last_name": "Karimov", "first_name": "Aziz", "phone": "+998901112233"})
    assert r.status_code == 201, r.text
    csv_text = "ID;F.I.SH;Telefon\n101;Karimov Aziz;+998901112233\n"
    b = await upload(hr, "employees", csv_text)
    r = await hr.put(f"{M}/batches/{b['id']}/mapping", json={"mapping": b["suggested"]})
    assert r.json()["summary"]["created"] == 0 and r.json()["summary"]["linked"] == 1
    await hr.post(f"{M}/batches/{b['id']}/apply")
    assert await count(Employee) == 1 and await count(MigrationLegacyId) == 1
    # davomat shu eski ID bo'yicha mavjud xodimga bog'lanadi
    a = await upload(hr, "attendance", "Xodim ID;Sana;Keldi;Ketdi\n101;01.10.2026;09:00;18:00\n")
    r = await hr.put(f"{M}/batches/{a['id']}/mapping", json={"mapping": a["suggested"]})
    assert r.json()["summary"]["created"] == 1


async def test_attendance_import_reconcile_and_rollback(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    await seed_org()
    e = await upload(hr, "employees", EMP_CSV)
    await hr.put(f"{M}/batches/{e['id']}/mapping", json={"mapping": e["suggested"], "options": {"create_missing": True}})
    await hr.post(f"{M}/batches/{e['id']}/apply")

    a = await upload(hr, "attendance", ATT_CSV)
    assert a["suggested"] == {"employee_ref": "Xodim ID", "work_date": "Sana", "check_in": "Keldi", "check_out": "Ketdi", "late_minutes": "Kechikish"}
    r = await hr.put(f"{M}/batches/{a['id']}/mapping", json={"mapping": a["suggested"], "options": {"match_by": "legacy_id"}})
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    # 101: 01.10 ok, 02.10 ok; 102: tungi smena ok; 101 01.10 takror -> skip; 999 noma'lum; 25:99 xato; 04.10 (48 soatlik smena) xato; 103 ketishsiz ok
    assert s["rows"] == 8 and s["created"] == 4 and s["errors"] == 3 and s["skipped"] == 1
    assert s["stats"]["reconciled"] is True
    assert await count(AttendanceRecord) == 0  # dry-run
    codes = {i["row"]: i["code"] for i in (await hr.get(f"{M}/batches/{a['id']}/issues")).json()["items"]}
    assert codes == {5: "attendance_exists", 6: "employee_unknown", 7: "time_invalid", 8: "shift_invalid"}

    r = await hr.post(f"{M}/batches/{a['id']}/apply")
    assert r.json()["status"] == "applied" and r.json()["summary"]["stats"]["db_minutes"] == 550 + 520 + 480
    async with SessionLocal() as db:
        recs = {(x.employee_id, x.work_date): x for x in (await db.scalars(select(AttendanceRecord))).all()}
    night = next(x for x in recs.values() if x.work_date == date(2026, 10, 1) and x.late_minutes == 0 and x.worked_minutes == 480)
    assert night.check_out_at.date() == date(2026, 10, 2) and night.in_method == "import" and night.is_manual
    assert sum(1 for x in recs.values() if x.late_minutes == 20) == 1

    # solishtirish
    for body in (
        {"label": "Xodimlar jami", "metric": "employees_total", "expected": 3},
        {"label": "Faol xodimlar", "metric": "employees_active", "expected": 3},
        {"label": "Oktyabr soat", "metric": "attendance_hours", "period": "2026-10", "expected": 25.83},
        {"label": "Oktyabr yozuv", "metric": "attendance_records", "period": "2026-10", "expected": 5, "tolerance": 0},
    ):
        assert (await hr.post(f"{M}/checks", json=body)).status_code == 201
    rec = (await hr.get(f"{M}/reconcile")).json()
    by = {x["label"]: x for x in rec["items"]}
    assert by["Xodimlar jami"]["status"] == "match" and by["Faol xodimlar"]["status"] == "mismatch" and by["Faol xodimlar"]["diff"] == -1.0
    assert by["Oktyabr soat"]["actual"] == 25.83 and by["Oktyabr soat"]["status"] == "match"
    assert by["Oktyabr yozuv"]["actual"] == 4 and by["Oktyabr yozuv"]["status"] == "mismatch"
    assert rec["matched"] == 2 and rec["mismatched"] == 2
    summ = (await hr.get(f"{M}/summary")).json()
    assert summ["applied_batches"] == 2 and summ["mismatched"] == 2

    # xodimlar paketini qaytarib bo'lmaydi: davomat shu xodimlarga bog'langan va boshqa paketdan
    r = await hr.post(f"{M}/batches/{e['id']}/rollback")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "batch_in_use"
    # avval davomat paketini qaytaramiz
    r = await hr.post(f"{M}/batches/{a['id']}/rollback")
    assert r.status_code == 200 and r.json()["summary"]["rolled_back"]["attendance"] == 4 and await count(AttendanceRecord) == 0
    assert (await hr.post(f"{M}/batches/{e['id']}/rollback")).status_code == 200


async def test_templates_and_checks_crud(new_client):
    hr, _ = await as_user(new_client, "hr", "hr_direktor")
    r = await hr.post(f"{M}/templates", json={"name": "Eski HR 1C", "dataset": "attendance", "mapping": {"work_date": "Sana", "employee_ref": "Tabel"}, "options": {"match_by": "employee_no"}})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert (await hr.post(f"{M}/templates", json={"name": "x", "dataset": "attendance", "mapping": {"nope": "A"}})).json()["detail"]["code"] == "unknown_field"
    assert (await hr.put(f"{M}/templates/{tid}", json={"name": "1C v2", "dataset": "attendance", "mapping": {"work_date": "Date"}})).json()["name"] == "1C v2"
    assert len((await hr.get(f"{M}/templates", params={"dataset": "attendance"})).json()) == 1
    assert (await hr.delete(f"{M}/templates/{tid}")).status_code == 204 and (await hr.get(f"{M}/templates/{tid}")).status_code == 404

    assert (await hr.post(f"{M}/checks", json={"label": "x", "metric": "attendance_hours", "expected": 1})).json()["detail"]["code"] == "period_required"
    assert (await hr.post(f"{M}/checks", json={"label": "x", "metric": "employees_total", "expected": 1, "branch_id": 9999})).json()["detail"]["code"] == "unknown_branch"
    c = (await hr.post(f"{M}/checks", json={"label": "Jami", "metric": "employees_total", "period": "2026-10", "expected": 0})).json()
    assert c["period"] is None  # xodimlar uchun davr kerak emas
    assert (await hr.put(f"{M}/checks/{c['id']}", json={"label": "Jami 2", "metric": "employees_total", "expected": 5, "tolerance": 5})).json()["label"] == "Jami 2"
    assert (await hr.get(f"{M}/reconcile")).json()["items"][0]["status"] == "match"  # tolerance ichida
    assert (await hr.delete(f"{M}/checks/{c['id']}")).status_code == 204

    await seed_org()
    csv_text = "label,metric,period,branch,expected,tolerance\nFilial 16 xodimlar,employees_active,,16,0,0\nOktyabr soat,attendance_hours,2026-10,,0,0.5\n"
    r = await hr.post(f"{M}/checks/import", files={"file": ("c.csv", csv_text.encode(), "text/csv")})
    assert r.status_code == 201 and r.json()["created"] == 2
    bad = await hr.post(f"{M}/checks/import", files={"file": ("c.csv", b"label,metric,expected\nx,nope,1\n", "text/csv")})
    assert bad.json()["detail"]["code"] == "metric_invalid"
    assert (await hr.get(f"{M}/reconcile")).json()["matched"] == 2
