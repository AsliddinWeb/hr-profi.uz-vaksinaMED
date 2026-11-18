from datetime import date

from sqlalchemy import text

from app.db import SessionLocal


def _g(title, metric, unit, baseline, target, deadline, specific, achievable=None, relevant=None):
    return {"title": title, "metric": metric, "unit": unit, "baseline": baseline, "target": target, "deadline": deadline.isoformat(), "specific": specific, "achievable": achievable, "relevant": relevant}


async def goals_flows(sd) -> None:
    print("G. SMART maqsadlar")
    y = date.today().year
    A = "demo_seeder"
    dept = sd.ids["dept"]
    koord, hrd, logist = sd.login_of("Yusupov"), sd.login_of("Aliyeva"), sd.login_of("Normatova")
    plans = {
        "Dorixonalar tarmog'i": (koord, "approved", [
            _g("Tarmoq savdosini oshirish", "Oylik savdo", "mln so'm", 820, 1000, date(y, 12, 31), "Barcha filiallarda oylik savdoni 1 mlrd so'mga yetkazish", "Assortimentni kengaytirish va 2 ta yangi filial", "Kompaniyaning yillik o'sish maqsadi"),
            _g("Mijozlar bahosini ko'tarish", "O'rtacha baho (QR)", "ball", 4.1, 4.6, date(y, 12, 31), "Mijozlar QR baholashida o'rtacha 4.6 ball", "Servis standartlari bo'yicha o'qitish", "Servis sifati — kompaniya qadriyati"),
            _g("Kechikishlarni kamaytirish", "Kechikkanlar ulushi", "%", 12, 4, date(y, 9, 30), "Smenaga kechikib keladigan xodimlar ulushini 4% gacha tushirish", "Face ID davomat va jarimalar tizimi"),
        ], [900, 4.4, 7]),
        "Moliya bo'limi": (A, "approved", [
            _g("Debitor qarzdorlikni qisqartirish", "Debitor qarz", "mln so'm", 340, 150, date(y, 12, 31), "Muddati o'tgan debitor qarzni 150 mln so'mgacha kamaytirish"),
            _g("Oylik hisobot muddati", "Hisobot tayyorlash", "kun", 10, 5, date(y, 6, 30), "Oylik moliyaviy hisobotni oy tugagach 5 kunda topshirish"),
        ], [210, 6]),
        "HR bo'limi": (hrd, "pending", [
            _g("Bo'sh o'rinlarni tez yopish", "Vakansiya yopilish muddati", "kun", 35, 20, date(y, 12, 31), "Vakansiyani o'rtacha 20 kunda yopish", "Rekruting voronkasi va AI suhbat", "Filiallar xodim bilan to'liq ta'minlanishi"),
            _g("Kadrlar qo'nimsizligini kamaytirish", "Yillik qo'nimsizlik", "%", 28, 18, date(y, 12, 31), "Yillik qo'nimsizlikni 18% gacha tushirish", "Onboarding va adaptatsiya dasturi"),
        ], None),
        "Logistika bo'limi": (logist, "draft", [
            _g("Yetkazib berish muddati", "O'rtacha yetkazish vaqti", "soat", 30, 24, date(y, 12, 31), "Filiallarga buyurtmani 24 soatda yetkazish"),
        ], None),
    }
    for name, (who, status, goals, progress) in plans.items():
        dept_id = dept.get(name)
        if not dept_id:
            continue
        url = f"/api/v1/org/goals/departments/{dept_id}"
        ids = [r["id"] for g in goals if (r := await sd.call(who, "POST", f"{url}?year={y}", json=g, label=f"maqsad {name}"))]
        if status in ("pending", "approved"):
            await sd.call(who, "POST", f"{url}/submit?year={y}", label=f"maqsadlar tasdiqqa {name}")
        if status == "approved":
            await sd.call(A, "POST", f"{url}/approve?year={y}", label=f"maqsadlar tasdiq {name}")
            for gid, cur in zip(ids, progress or [], strict=False):
                await sd.call(who, "PUT", f"/api/v1/org/goals/items/{gid}/progress", json={"current": cur}, label="progress")
        if name == "Dorixonalar tarmog'i" and ids:
            changed = {**goals[0], "target": 1150, "achievable": "Assortiment, 2 ta yangi filial va yetkazib berish xizmati"}
            await sd.call(who, "POST", f"{url}/changes?year={y}", json={"action": "update", "goal_id": ids[0], "values": changed, "reason": "Yetkazib berish xizmati ishga tushdi, savdo rejadan tez o'smoqda"}, label="maqsad istisno so'rovi")
    async with SessionLocal() as s:
        await s.execute(text(
            "UPDATE goal_plans SET approved_by = (SELECT u.id FROM users u JOIN roles r ON r.id = u.role_id WHERE r.key = 'tasischi' AND u.login <> 'demo_seeder' ORDER BY u.id LIMIT 1) "
            "WHERE approved_by = (SELECT id FROM users WHERE login = 'demo_seeder')"
        ))  # fmt: skip
        await s.commit()
