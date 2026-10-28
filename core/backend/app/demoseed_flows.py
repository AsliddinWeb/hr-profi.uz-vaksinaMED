"""Demo seed: bo'limlar bo'yicha ish oqimlari (REST API orqali). `demoseed.Seeder` ga tayanadi."""

from datetime import date, datetime, timedelta

from app.timeutil import tz


def _items(r):
    return r if isinstance(r, list) else (r or {}).get("items", [])


async def flows(sd) -> None:  # noqa: C901
    today = date.today()
    now = datetime.now(tz())
    A = "demo_seeder"
    hrd, hrm = sd.login_of("Aliyeva"), sd.login_of("Rustamova")
    koord, mudir1, mudir2 = sd.login_of("Yusupov"), sd.login_of("Ergashev"), sd.login_of("Nazarova")
    f1, f2, f3 = sd.login_of("Soliyeva"), sd.login_of("Tursunov"), sd.login_of("Umarova")
    ayti, logist, resep = sd.login_of("Orifov"), sd.login_of("Normatova"), sd.login_of("Jo'rayeva")

    users = {u["login"]: u for u in _items(await sd.call(A, "GET", "/api/v1/users?limit=200", label="users"))}
    uid = lambda login: users[login]["id"]  # noqa: E731
    emps = _items(await sd.call(A, "GET", "/api/v1/employees?limit=200", label="employees"))
    eid = {e["last_name"]: e["id"] for e in emps}
    br = sd.ids["branch"]

    # filial mas'ullari: mudir va koordinator
    for bno, mu in ((16, mudir1), (36, mudir2), (11, mudir1), (6, mudir1), (67, mudir2)):
        await sd.call(A, "PATCH", f"/api/v1/branches/{br[bno]}", json={"manager_user_id": uid(mu), "coordinator_user_id": uid(koord)}, label="filial mas'ul")
    await sd.call(A, "PUT", f"/api/v1/logistics/drivers/{eid['Xolmatov']}", json={"license_no": "AB 1234567", "categories": "B", "license_expires": str(today + timedelta(days=700))}, label="haydovchi")

    # 4. Davomat muammosi: xodim -> koordinator tasdiqlaydi -> HR hal qiladi
    print("4. Davomat muammosi")
    y = today - timedelta(days=1)
    for who, kind, cmt in [(f1, "missed_in", "Face ID ishlamadi, telefon kamerasi xira edi"), (f2, "missed_out", "Smena oxirida QR kod ochilmadi")]:
        i = await sd.call(who, "POST", "/api/v1/attendance-issues", json={"work_date": str(y), "kind": kind, "method_tried": "face",
              "claimed_in": datetime(y.year, y.month, y.day, 9, 0, tzinfo=tz()).isoformat() if kind == "missed_in" else None,
              "claimed_out": datetime(y.year, y.month, y.day, 18, 0, tzinfo=tz()).isoformat() if kind == "missed_out" else None, "comment": cmt}, label="muammo")
        if i and who == f1:
            await sd.call(koord, "POST", f"/api/v1/attendance-issues/{i['id']}/verify", json={"action": "confirm", "note": "Filialda ekanini tasdiqlayman"}, label="verify")
            await sd.call(hrd, "POST", f"/api/v1/attendance-issues/{i['id']}/decide", json={"action": "approve", "note": "Qabul qilindi"}, label="decide")

    # 5. Ta'til/javob so'rovi
    print("5. So'rovlar, topshiriqlar, eslatmalar")
    await sd.call(f3, "POST", "/api/v1/answers/requests", json={"kind": "day", "reason_type": "family", "start_date": str(today + timedelta(days=3)), "end_date": str(today + timedelta(days=4)), "reason": "Oilaviy tadbir"}, label="so'rov")
    # topshiriqlar
    for title, who, pr, days in [("Filial 16 invertarizatsiyasi", mudir1, "high", 3), ("Yangi xodimlar uchun forma buyurtmasi", hrm, "normal", 7), ("Dori muddatini tekshirish", f1, "high", 2), ("Oylik hisobotni topshirish", mudir2, "normal", 5)]:
        await sd.call(hrd, "POST", "/api/v1/tasks", json={"title": title, "description": "Namunaviy topshiriq", "priority": pr, "due_at": (now + timedelta(days=days)).isoformat(), "assignee_id": uid(who)}, label="topshiriq")
    await sd.call(hrm, "POST", "/api/v1/reminders", json={"title": "Oy oxirida attestatsiya natijalarini ko'rib chiqish", "first_at": (now + timedelta(days=2)).isoformat(), "repeat": "monthly", "interval": 1, "recipients": [uid(hrm)]}, label="eslatma")

    # 6. Yordam markazi (AyTi) va ehtiyojlar (zayafka)
    print("6. Yordam markazi, zayafka")
    c1 = await sd.call(A, "POST", "/api/v1/helpdesk/categories", json={"name": "Kompyuter/printer", "default_assignee_id": uid(ayti)}, label="kategoriya")
    await sd.call(A, "POST", "/api/v1/helpdesk/categories", json={"name": "Dastur/1C", "default_assignee_id": uid(ayti)}, label="kategoriya")
    for who, t, d, b in [(mudir1, "Printer chop etmayapti", "Cheklar chiqmayapti", 16), (f2, "Kompyuter sekin ishlayapti", "Dastur qotib qolyapti", 16), (mudir2, "Internet uzilib qoldi", "Tunuka ichida signal yo'q", 36)]:
        await sd.call(who, "POST", "/api/v1/helpdesk", json={"title": t, "description": d, "category_id": c1["id"] if c1 else None, "branch_id": br[b], "priority": "high" if "Internet" in t else "normal"}, label="ticket")
    nc = await sd.call(A, "POST", "/api/v1/needs/categories", json={"name": "Xo'jalik buyumlar", "sla_days": 5}, label="ehtiyoj kat.")
    for who, t, b in [(mudir1, "Kassa lentasi (20 dona)", 16), (mudir2, "Konditsioner ta'miri", 36), (f1, "Yangi xalat (3 dona)", 16)]:
        await sd.call(who, "POST", "/api/v1/needs", json={"title": t, "category_id": nc["id"] if nc else None, "branch_id": br[b], "priority": "normal"}, label="ehtiyoj")

    # 7. Xodim zayafkasi -> vakansiya -> nomzod -> suhbat -> offer
    print("7. Rekrut: zayafka, vakansiya, nomzodlar")
    pos = sd.ids["pos"]
    farm_pos = pos.get(("Farmasevt", "Dorixona tarmog'i"))
    for who, b, role, cnt, reason in [(mudir1, 16, "pharmacist", 2, "Xodim ta'tilga chiqdi"), (mudir2, 36, "pharmacist", 1, "Yangi smena ochilmoqda")]:
        await sd.call(who, "POST", "/api/v1/pharmacy/needs", json={"branch_id": br[b], "role": role, "count": cnt, "urgency": "normal", "needed_from": str(today + timedelta(days=10)), "reason": reason, "reason_type": "departure", "position_id": farm_pos}, label="xodim zayafkasi")
    vac = await sd.call(hrm, "POST", "/api/v1/recruit/vacancies", json={"title": "Farmasevt (Yunusobod)", "branch_id": br[16], "department_id": sd.ids["dept"]["Dorixona tarmog'i"], "position_id": farm_pos,
                         "description": "Dorixonada mijozlarga xizmat ko'rsatish", "requirements": "O'rta maxsus farmatsevtik ma'lumot, mas'uliyat", "salary_from": 3500000, "salary_to": 5000000, "openings": 2, "recruiter_id": uid(hrm), "deadline": str(today + timedelta(days=20))}, label="vakansiya")
    if vac:
        await sd.call(hrm, "POST", f"/api/v1/recruit/vacancies/{vac['id']}/status", json={"status": "open"}, label="vakansiyani ochish")
    cands = []
    for name, ph, src, skills in [("Karimova Feruza", "+998931110001", "hh", "Farmatsevt diplomi, 2 yil tajriba"), ("Sodiqov Akmal", "+998931110002", "telegram", "Dori vositalari, kassa"), ("Hasanova Nigora", "+998931110003", "olx", "Yangi bitiruvchi, ishtiyoqli"), ("Boboyev Sanjar", "+998931110004", "referral", "Savdo tajribasi")]:
        c = await sd.call(hrm, "POST", "/api/v1/recruit/candidates", json={"full_name": name, "phone": ph, "source": src, "skills": [s.strip() for s in skills.split(",")]}, label="nomzod")
        cands.append(c)
        if c and vac:
            ap = await sd.call(hrm, "POST", "/api/v1/recruit/applications", json={"vacancy_id": vac["id"], "candidate_id": c["id"]}, label="ariza")
            if ap and name.startswith("Karimova"):
                await sd.call(hrm, "POST", f"/api/v1/recruit/applications/{ap['id']}/interview", json={"experience_level": "high", "hard_skill": 4, "soft_skill": 5, "notes": "Yaxshi muloqot, tajribali"}, label="suhbat")
                await sd.call(hrm, "POST", f"/api/v1/recruit/applications/{ap['id']}/offer", json={"level": "pharmacist", "salary": 4200000, "note": "Sinov muddati 1 oy"}, label="offer")
    await sd.call(hrm, "POST", "/api/v1/recruit/calls", json={"outcome": "callback", "phone": "+998931110009", "vacancy_id": vac["id"] if vac else None, "note": "Ertaga suhbatga keladi"}, label="qo'ng'iroq")

    # 8. Stajirovka va onboarding
    print("8. Stajirovka")
    prog = await sd.call(hrd, "POST", "/api/v1/internship/programs", json={"name": "Yangi farmasevt 14 kunlik dasturi", "description": "Dorixona asoslari, kassa, mijoz bilan muloqot", "pass_score": 70, "sequential": True, "phase": "onboarding", "duration_days": 14}, label="dastur")
    if prog:
        pid = prog["id"]
        await sd.call(hrd, "POST", f"/api/v1/internship/programs/{pid}/steps", json={"kind": "video", "title": "Dorixona bilan tanishuv", "url": "https://example.com/intro", "description": "Kompaniya va filial tartiblari"}, label="qadam")
        await sd.call(hrd, "POST", f"/api/v1/internship/programs/{pid}/steps", json={"kind": "text", "title": "Mijoz bilan muloqot qoidalari", "description": "Salomlashish, ehtiyojni aniqlash, xayrlashish"}, label="qadam")
        await sd.call(hrd, "POST", f"/api/v1/internship/programs/{pid}/steps", json={"kind": "test", "title": "Yakuniy test", "pass_score": 70, "questions": [
            {"text": "Retseptsiz dori sotishda birinchi navbatda nima qilinadi?", "options": ["Narxini aytish", "Mijoz ehtiyojini so'rash", "Boshqasini taklif qilish"], "correct": [1]},
            {"text": "Dori muddatini qachon tekshiramiz?", "options": ["Faqat yilda bir marta", "Har kuni/har qabulda", "Hech qachon"], "correct": [1]}]}, label="test")
        for who in ("Ismoilova", "Abdullayev"):
            await sd.call(hrd, "POST", "/api/v1/internship/enrollments", json={"program_id": prog["id"], "employee_id": eid[who], "mentor_id": uid(mudir1), "due_date": str(today + timedelta(days=14))}, label="stajyor")
        await sd.call(hrd, "POST", "/api/v1/internship/classes", json={"title": "Kassa bilan ishlash", "starts_at": (now + timedelta(days=2)).isoformat(), "place": "Bosh ofis o'quv xonasi", "employee_ids": [eid["Ismoilova"], eid["Abdullayev"]]}, label="dars")

    # 9. O'sish: zinapoya, promotion
    print("9. O'sish, attestatsiya")
    lv = await sd.call(hrd, "PUT", "/api/v1/growth/levels", json={"levels": [{"name": "Stajyor"}, {"name": "Farmasevt"}, {"name": "Katta farmasevt", "salary_min": 4500000, "salary_max": 6000000}, {"name": "Mudir", "salary_min": 6000000, "salary_max": 9000000}]}, label="zinapoya")
    levels = _items(lv) or (lv or {}).get("levels", []) if lv else []
    if len(levels) >= 3:
        await sd.call(hrd, "POST", "/api/v1/growth/promotions", json={"employee_id": eid["Soliyeva"], "to_level_id": levels[2]["id"], "basis": "Oxirgi 3 oy a'lo natija"}, label="o'sish")
    await sd.call(hrd, "POST", "/api/v1/attestation/cycles", json={}, label="attestatsiya sikli")

    # 10. Ushlab qolish va ishdan ketish
    print("10. Ushlab qolish")
    case = await sd.call(hrm, "POST", "/api/v1/retention/cases", json={"employee_id": eid["Hamidov"], "note": "Maosh ko'tarilishini so'radi, boshqa joyga taklif bor", "risk_level": "high"}, label="ushlab qolish")
    if case:
        await sd.call(hrm, "POST", "/api/v1/retention/meetings", json={"held_on": str(today), "summary": "Haftalik uchrashuv: xavf ostidagi xodimlar muhokama qilindi", "case_ids": [case["id"]]}, label="uchrashuv")
    await sd.call(hrd, "POST", "/api/v1/offboarding", json={"employee_id": eid["Qodirova"], "leave_date": str(today + timedelta(days=10))}, label="offboarding")

    # 11. Shikoyat, tushuntirish xati, jarima
    print("11. Shikoyat, intizom")
    await sd.call(f2, "POST", "/api/v1/complaints", json={"category": "conditions", "title": "Filialda konditsioner ishlamayapti", "text": "Yozda smena paytida issiqdan ishlash qiyin", "is_anonymous": True}, label="shikoyat")
    await sd.call(hrm, "POST", "/api/v1/letters", json={"employee_id": eid["Saidov"], "incident_type": "late", "incident_date": str(y), "incident_note": "35 daqiqa kechikdi"}, label="tushuntirish xati")
    await sd.call(hrd, "POST", "/api/v1/penalties", json={"employee_id": eid["Tursunov"], "incident_type": "late", "incident_date": str(y - timedelta(days=2)), "reason": "Bir oyda 3 marta kechikish", "step": 1, "amount": 50000}, label="jarima")

    # 12. Ish haqi
    print("12. Ish haqi")
    period = today.strftime("%Y-%m")
    for last, amt in [("Soliyeva", 4000000), ("Tursunov", 3800000), ("Umarova", 3800000), ("Saidov", 3600000)]:
        await sd.call(hrd, "POST", "/api/v1/payroll/schemes", json={"employee_id": eid[last], "effective_from": str(today.replace(day=1)), "fixed_amount": amt, "commission_percent": 1.5}, label="oylik sxema")
    await sd.call(hrd, "POST", "/api/v1/payroll/items", json={"employee_id": eid["Soliyeva"], "period": period, "kind": "bonus", "amount": 300000, "note": "Reja ortig'i bilan bajarildi"}, label="mukofot")
    await sd.call(hrd, "POST", "/api/v1/payroll/runs", json={"period": period}, label="oylik hisoblash")

    # 13. Oshxona, logistika, ombor, resepshn, nazorat ro'yxati
    print("13. Oshxona, logistika, ombor, resepshn, tekshiruv")
    await sd.call(hrm, "POST", "/api/v1/canteen/menus", json={"menu_date": str(today), "dishes": [{"name": "Mastava", "kind": "soup"}, {"name": "Palov", "kind": "main"}, {"name": "Achchiq-chuchuk", "kind": "salad"}, {"name": "Kompot", "kind": "drink"}]}, label="menyu")
    veh = await sd.call(logist, "POST", "/api/v1/logistics/vehicles", json={"plate": "01 A 777 AA", "name": "Damas (yetkazib berish)", "kind": "van", "fuel_type": "gas", "tank_l": 40, "odometer_km": 85000}, label="mashina")
    if veh:
        await sd.call(logist, "POST", "/api/v1/logistics/trips", json={"vehicle_id": veh["id"], "driver_id": eid["Xolmatov"], "purpose": "Filiallarga dori yetkazish", "origin": "Markaziy ombor", "destination": "Yunusobod-15"}, label="reys")
        await sd.call(logist, "POST", "/api/v1/logistics/fuel", json={"vehicle_id": veh["id"], "liters": 30, "price_per_liter": 5800, "odometer_km": 85120, "station": "Metan shoxobchasi"}, label="yoqilg'i")
    await sd.call(A, "POST", "/api/v1/warehouse", json={"name": "Markaziy ombor", "min_on_duty": 1, "max_shift_hours": 12}, label="ombor")
    await sd.call(resep, "POST", "/api/v1/reception", json={"visitor_name": "Qodirov Anvar", "company": "Pharm-Trade", "purpose": "meeting", "note": "Shartnoma muhokamasi", "host_id": eid["Karimov"], "expected_at": now.isoformat()}, label="mehmon")
    tpl = await sd.call(hrd, "POST", "/api/v1/checklists/templates", json={"name": "Filial kunlik tekshiruvi", "items": [{"text": "Toza va tartibli", "kind": "yesno"}, {"text": "Narx yorliqlari to'g'ri", "kind": "yesno"}, {"text": "Xodimlar formada", "kind": "yesno"}, {"text": "Umumiy baho", "kind": "score"}]}, label="tekshiruv shabloni")
    if tpl:
        await sd.call(koord, "POST", "/api/v1/checklists/visits", json={"branch_id": br[16], "template_id": tpl["id"], "latitude": 41.3606, "longitude": 69.2862}, label="filial tekshiruvi")

    # 14. Bildirishnoma, hisobot, integratsiya
    print("14. Bildirishnoma, hisobot, integratsiya")
    await sd.call(hrd, "POST", "/api/v1/notifications/broadcast", json={"title": "Yangi tizimga xush kelibsiz", "body": "Bugundan davomat va topshiriqlar HR-Profi orqali yuritiladi", "everyone": True}, label="e'lon")
    await sd.call(hrd, "POST", "/api/v1/reports/schedules", json={"name": "Haftalik davomat", "report_type": "attendance", "frequency": "weekly", "weekday": 0, "recipient_ids": [uid(hrd)]}, label="hisobot jadvali")
    await sd.call(A, "POST", "/api/v1/integrations/keys", json={"name": "Dori tizimi (demo)", "scopes": ["branches:read"]}, label="API kalit")

    # 15. Rotatsiya: HR faol rotatsiya yaratdi, mudir so'rov yubordi (HR tasdig'ini kutmoqda)
    print("15. Rotatsiya")
    await sd.call(hrd, "POST", "/api/v1/rotations", json={"employee_id": eid["Saidov"], "to_branch_id": br[16], "start_date": str(today), "end_date": str(today + timedelta(days=7)), "reason": "1-gor bolnitsada smena yetishmayapti"}, label="rotatsiya (faol)")
    await sd.call(mudir2, "POST", "/api/v1/rotations", json={"employee_id": eid["Hamidov"], "to_branch_id": br[36], "start_date": str(today + timedelta(days=3)), "end_date": str(today + timedelta(days=10)), "reason": "Yakkasaroy filialida ta'mirlash"}, label="rotatsiya (so'rov)")
