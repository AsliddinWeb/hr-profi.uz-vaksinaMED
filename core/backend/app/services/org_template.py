"""Kompaniya tashkiliy tuzilmasi shabloni (mijozning "org.xlsx" shajarasi asosida) va uni bazaga qo'llash.

Har bir bo'lim: nomi, ota bo'lim, qaysi lavozim ostida chiziladi (`under`), lavozimlar shajarasi:
(lavozim, kimga bo'ysunadi, shtat soni, boshliqmi). Qo'llash idempotent: borini o'zgartirmaydi, yo'g'ini qo'shadi,
bo'ysunish va shtat sonini shablonga moslaydi.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import Department, Position

H = True  # boshliq lavozimi

VAKSINA_ORG: list[dict[str, Any]] = [
    {"name": "Rahbariyat", "color": "#1e2a78", "positions": [
        ("Ta'sischi", None, 1, H), ("Ta'sischining asistenti", "Ta'sischi", 1, False), ("Direktor (CEO)", "Ta'sischi", 1, False),
    ]},
    {"name": "Moliya bo'limi", "parent": "Rahbariyat", "under": "Ta'sischi", "color": "#12a150", "positions": [
        ("Moliya bo'limi boshlig'i", None, 1, H), ("Bosh buxgalter", "Moliya bo'limi boshlig'i", 1, False),
        ("Moddiy buxgalter", "Moliya bo'limi boshlig'i", 1, False), ("Buxgalter-kassir", "Bosh buxgalter", 1, False), ("Kassir", "Moddiy buxgalter", 1, False),
    ]},
    {"name": "Texnika bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#8b5cf6", "positions": [
        ("Bosh oshpaz", None, 1, H), ("Oshpaz yordamchisi", "Bosh oshpaz", 2, False), ("Tozalovchi", "Bosh oshpaz", 1, False),
    ]},
    {"name": "SB bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#6b7280", "positions": [
        ("SB bo'limi boshlig'i", None, 1, H), ("Videokuzatuv operatori", "SB bo'limi boshlig'i", 3, False),
    ]},
    {"name": "Ta'minot bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#e8590c", "positions": [
        ("Ta'minot bo'limi boshlig'i", None, 1, H), ("Ta'minot xodimi", "Ta'minot bo'limi boshlig'i", 6, False),
    ]},
    {"name": "Omborxona bo'limi", "parent": "Ta'minot bo'limi", "under": "Ta'minot bo'limi boshlig'i", "color": "#64748b", "kind": "warehouse", "positions": [
        ("Omborxona bo'limi boshlig'i", None, 1, H), ("Omborxona mudiri o'rinbosari", "Omborxona bo'limi boshlig'i", 1, False),
        ("Omborxona mudiri (kirim)", "Omborxona bo'limi boshlig'i", 1, False),
        ("Tovar yig'uvchi xodim", "Omborxona mudiri o'rinbosari", 13, False), ("Tovar yig'uvchi xodim (kirim)", "Omborxona mudiri (kirim)", 12, False),
    ]},
    {"name": "Logistika bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#f59e0b", "positions": [
        ("Logistika va mexanik boshlig'i", None, 1, H), ("Shafyor", "Logistika va mexanik boshlig'i", 24, False),
    ]},
    {"name": "HR bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#2563eb", "positions": [
        ("HRD (HR direktor)", None, 1, H), ("HR auditor", "HRD (HR direktor)", 1, False), ("Kadrovik", "HR auditor", 1, False),
        ("HR menejer", "HRD (HR direktor)", 2, False), ("HR rekruter", "HR menejer", 2, False), ("Farm trener", "HR rekruter", 2, False),
        ("Koordinator (shahar)", "HRD (HR direktor)", 4, False),
        ("Koordinator (Andijon)", "HRD (HR direktor)", 1, False), ("Koordinator (Qoraqalpog'iston)", "HRD (HR direktor)", 1, False),
        ("Koordinator (Qashqadaryo)", "HRD (HR direktor)", 1, False), ("Koordinator (Namangan)", "HRD (HR direktor)", 1, False),
        ("Koordinator (Samarqand)", "HRD (HR direktor)", 1, False), ("Koordinator (Farg'ona)", "HRD (HR direktor)", 1, False),
        ("Koordinator (Surxondaryo)", "HRD (HR direktor)", 1, False), ("Koordinator (Sirdaryo)", "HRD (HR direktor)", 1, False),
    ]},
    {"name": "Dorixonalar tarmog'i", "parent": "HR bo'limi", "under": "Koordinator (shahar)", "color": "#0d9488", "kind": "pharmacy", "positions": [
        ("Mudir", None, 0, H), ("Farmatsevt", "Mudir", 0, False), ("Stajyor", "Farmatsevt", 0, False),
    ]},
    {"name": "IT bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#0891b2", "positions": [
        ("IT bo'lim boshlig'i", None, 1, H), ("Dasturchi", "IT bo'lim boshlig'i", 1, False), ("Tarmoq administratori", "IT bo'lim boshlig'i", 3, False),
    ]},
    {"name": "Reviziya bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#7c3aed", "positions": [
        ("Reviziya bo'lim boshlig'i", None, 1, H), ("Revizor mutaxassis", "Reviziya bo'lim boshlig'i", 4, False),
    ]},
    {"name": "AXO bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#db2777", "positions": [("AXO bo'lim boshlig'i", None, 1, H)]},
    {"name": "GPP bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#be185d", "positions": [
        ("GPP bo'lim boshlig'i", None, 1, H), ("GPP mutaxassis", "GPP bo'lim boshlig'i", 1, False),
    ]},
    {"name": "Rivojlanish bo'limi", "parent": "Rahbariyat", "under": "Direktor (CEO)", "color": "#16a34a", "positions": [
        ("Rivojlanish bo'lim boshlig'i", None, 1, H), ("Muhandis-loyihachi", "Rivojlanish bo'lim boshlig'i", 1, False),
        ("Hududlarni rivojlantirish menejeri", "Muhandis-loyihachi", 1, False), ("Prorab", "Hududlarni rivojlantirish menejeri", 1, False),
        ("Servis muhandisi", "Prorab", 1, False),
    ]},
    {"name": "Qurilish bo'limi", "parent": "Rivojlanish bo'limi", "under": "Rivojlanish bo'lim boshlig'i", "color": "#65a30d", "positions": [
        ("Qurilish bo'lim boshlig'i", None, 1, H), ("Qurilish xodimi", "Qurilish bo'lim boshlig'i", 1, False),
    ]},
]  # fmt: skip


async def apply_org_template(db: AsyncSession, template: list[dict[str, Any]] = VAKSINA_ORG) -> dict[str, int]:
    """Shablonni bazaga qo'llaydi (nom bo'yicha topadi yoki yaratadi). Commit chaqiruvchida."""
    depts = {d.name: d for d in (await db.scalars(select(Department))).all()}
    created = {"departments": 0, "positions": 0}
    for i, spec in enumerate(template):
        d = depts.get(spec["name"])
        if d is None:
            d = Department(name=spec["name"], kind=spec.get("kind", "office"), color=spec.get("color"), sort_order=i)
            db.add(d)
            created["departments"] += 1
            depts[d.name] = d
        if spec.get("parent"):
            await db.flush()
            d.parent_id = depts[spec["parent"]].id
    await db.flush()
    pos_by_name: dict[str, Position] = {}
    for spec in template:
        d = depts[spec["name"]]
        existing = {p.name: p for p in (await db.scalars(select(Position).where(Position.department_id == d.id))).all()}
        for j, (name, _parent, slots, head) in enumerate(spec["positions"]):
            p = existing.get(name)
            if p is None:
                p = Position(name=name, department_id=d.id, sort_order=j)
                db.add(p)
                created["positions"] += 1
            p.slots, p.is_head, p.sort_order = slots, head, j
            pos_by_name[name] = p
    await db.flush()
    for spec in template:
        for name, parent, _slots, _head in spec["positions"]:
            pos_by_name[name].parent_id = pos_by_name[parent].id if parent else None
        if spec.get("under"):
            depts[spec["name"]].reports_to_position_id = pos_by_name[spec["under"]].id
    await db.flush()
    return created
