"""Demo seed (2-qism): yangi bo'limlar — zayafkalar, avto-havolalar, 8 bosqichli anketa, kiruvchi/chiquvchi qo'ng'iroqlar,
ishga qabul (Shaxsiy ish), mehnat shartnomalari, prebording, lavozimlar va to'liq bajarilgan topshiriqlar."""

from datetime import date, datetime, timedelta

from app.timeutil import tz

ANKETA = [
    ("Xamrayeva Dilfuza", "+998901110001", {"specialty": "Farmatsiya", "education_place": "Toshkent farmatsevtika instituti", "graduation_year": "2019", "last_job": "Grand Pharm", "last_position": "Farmatsevt", "experience_years": "5", "computer_skill": "Yaxshi", "gmp_certificate": "Bor", "drug_knowledge": "Yuqori", "shift": "Ertalabki", "salary_text": "7-8 mln", "motivation": "Katta tarmoqda o'sish"}),
    ("Qosimov Jahongir", "+998901110002", {"specialty": "Farmatsiya", "education_place": "Samarqand tibbiyot kolleji", "graduation_year": "2021", "last_job": "Dorixona 24", "last_position": "Sotuvchi-farmatsevt", "experience_years": "3", "computer_skill": "O'rta", "gmp_certificate": "Yo'q", "drug_knowledge": "O'rta", "shift": "Kechki", "salary_text": "5-6 mln"}),
    ("Yo'ldosheva Sevinch", "+998901110003", {"specialty": "Davolash ishi", "education_place": "TTA", "graduation_year": "2023", "experience_years": "1", "computer_skill": "Yaxshi", "drug_knowledge": "O'rta", "shift": "Navbatma-navbat", "salary_text": "Kelishiladi"}),
    ("Raximov Sardor", "+998901110004", {"specialty": "Sanoat farmatsiya", "education_place": "Toshkent farmatsevtika instituti", "graduation_year": "2018", "last_job": "Oxy Med", "last_position": "Mudir o'rinbosari", "experience_years": "7", "computer_skill": "Yaxshi", "gmp_certificate": "Bor", "drug_knowledge": "Yuqori", "shift": "Farqi yo'q", "salary_text": "9 mln"}),
    ("Tojiboyeva Malika", "+998901110005", {"specialty": "Farmatsiya", "education_place": "Navoiy tibbiyot kolleji", "graduation_year": "2024", "experience_years": "0", "computer_skill": "O'rta", "shift": "Ertalabki", "salary_text": "4 mln"}),
    ("Abdurahmonov Ulug'bek", "+998901110006", {"specialty": "Farmatsiya", "education_place": "Andijon tibbiyot instituti", "graduation_year": "2020", "last_job": "Pharma Cosmos", "last_position": "Farmatsevt", "experience_years": "4", "computer_skill": "Yaxshi", "gmp_certificate": "Bor", "drug_knowledge": "Yuqori", "shift": "Kechki", "salary_text": "6-7 mln"}),
]
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _items(r):
    return r if isinstance(r, list) else (r or {}).get("items", [])


async def more_flows(sd) -> None:  # noqa: C901
    today = date.today()
    now = datetime.now(tz())
    A = "demo_seeder"
    hrd, hrm = sd.login_of("Aliyeva"), sd.login_of("Rustamova")
    mudir1, koord = sd.login_of("Ergashev"), sd.login_of("Yusupov")
    f1, f2, f3 = sd.login_of("Soliyeva"), sd.login_of("Tursunov"), sd.login_of("Umarova")
    users = {u["login"]: u for u in _items(await sd.call(A, "GET", "/api/v1/users?limit=200", label="users"))}
    uid = lambda login: users[login]["id"]  # noqa: E731
    emps = _items(await sd.call(A, "GET", "/api/v1/employees?limit=200", label="employees"))
    eid = {e["last_name"]: e["id"] for e in emps}
    dept, br = sd.ids["dept"], sd.ids["branch"]

    # Umumiy lavozimlar (bo'limsiz) — yangi "Lavozimlar" sahifasi uchun
    print("A. Umumiy lavozimlar")
    for name in ("Kassir", "Farrosh", "Qo'riqchi"):
        await sd.call(A, "POST", "/api/v1/org/positions", json={"name": name, "department_id": None}, label=f"umumiy lavozim {name}")
    positions = _items(await sd.call(A, "GET", "/api/v1/org/positions", label="lavozimlar"))
    pos = {p["name"]: p["id"] for p in positions}

    # Bo'lim boshliqlari (zayafka bera olishi uchun)
    pharm_dept, log_dept = dept["Dorixona tarmog'i"], dept["Logistika"]
    await sd.call(A, "PATCH", f"/api/v1/org/departments/{pharm_dept}", json={"head_user_id": uid(koord)}, label="bo'lim boshlig'i")
    await sd.call(A, "PATCH", f"/api/v1/org/departments/{log_dept}", json={"head_user_id": uid(sd.login_of("Normatova"))}, label="bo'lim boshlig'i")

    # B. Zayafkalar: tasdiqlangan, kutilayotgan, rad etilgan
    print("B. Zayafkalar")
    reqs = []
    for who, body in [
        (koord, {"department_id": dept["Dorixona tarmog'i"], "position_id": pos.get("Farmasevt"), "count": 3, "urgency": "urgent", "needed_from": str(today + timedelta(days=10)), "reason": "Yangi 2 ta filial ochilmoqda", "salary_from": 6_000_000, "salary_to": 8_000_000}),
        (koord, {"department_id": dept["Dorixona tarmog'i"], "position_id": pos.get("Mudir"), "count": 1, "reason": "Filial 36 mudiri dekretga chiqadi"}),
        (sd.login_of("Normatova"), {"department_id": dept["Logistika"], "position_id": pos.get("Haydovchi"), "count": 1, "reason": "Qo'shimcha reys"}),
    ]:
        if body["position_id"]:
            r = await sd.call(who, "POST", "/api/v1/recruit/requests", json=body, label="zayafka")
            if r:
                reqs.append(r)
    vid = None
    if reqs:
        ok = await sd.call(hrd, "POST", f"/api/v1/recruit/requests/{reqs[0]['id']}/decide", json={"action": "approve", "note": "Ochildi", "recruiter_id": uid(hrm)}, label="zayafka tasdiq")
        vid = (ok or {}).get("vacancy_id")
    if len(reqs) > 2:
        await sd.call(hrd, "POST", f"/api/v1/recruit/requests/{reqs[2]['id']}/decide", json={"action": "reject", "note": "Budjet keyingi chorakda"}, label="zayafka rad")

    # C. Avto-havolalar orqali anketa (8 bosqich) va qo'ng'iroqlar
    if vid:
        print("C. Anketalar va qo'ng'iroqlar")
        dash = await sd.call(hrm, "GET", f"/api/v1/recruit/vacancies/{vid}/dashboard", label="vakansiya paneli")
        links = {lk["channel"]: lk["code"] for lk in (dash or {}).get("links", [])}
        anon = sd._mk()
        for n, (name, phone, ank) in enumerate(ANKETA):
            code = links.get("site" if n % 2 == 0 else "telegram")
            if not code:
                continue
            await anon.get(f"/api/v1/public/apply/{code}")
            r = (await anon.post(f"/api/v1/public/apply/{code}", json={"full_name": name, "phone": phone})).json()
            url = r.get("profile_url")
            if not url:
                continue
            token = url.rsplit("/", 1)[1]
            await anon.put(f"/api/v1/public/profile/{token}", json={"full_name": name, "email": f"nomzod{n}@mail.uz", "address": "Toshkent", "languages": ["rus"], "skills": [], "anketa": ank})
            if n != 4:  # bittasi anketani oxirigacha yubormagan (holat ko'rinishi uchun)
                await anon.post(f"/api/v1/public/profile/{token}/confirm")
        await anon.aclose()
        for n, (direction, outcome) in enumerate([("out", "suitable"), ("out", "no_answer"), ("in", "suitable"), ("out", "unsuitable"), ("in", "callback"), ("out", "suitable"), ("out", "no_answer"), ("in", "unsuitable")]):
            await sd.call(hrm, "POST", "/api/v1/recruit/calls", json={"outcome": outcome, "direction": direction, "vacancy_id": vid, "phone": ANKETA[n % len(ANKETA)][1], "note": "Telefon suhbati"}, label="qo'ng'iroq")

    # D. Ishga qabul: offer qabul qilgan nomzod -> xodim (Shaxsiy ish to'ladi)
    print("D. Ishga qabul va Shaxsiy ish")
    offered = _items(await sd.call(hrm, "GET", "/api/v1/recruit/applications?stage=offer", label="offer bosqichi"))
    for a in offered[:1]:
        await sd.call(hrd, "POST", f"/api/v1/recruit/applications/{a['id']}/hire", json={"hire_date": str(today - timedelta(days=5)), "branch_id": br.get(16), "department_id": dept["Dorixona tarmog'i"], "position_id": pos.get("Farmasevt"), "confirm_duplicate": True}, label="ishga olish")
    # mehnat shartnomalari (Shaxsiy ish -> Shartnoma)
    for last in ("Soliyeva", "Tursunov", "Umarova", "Ergashev", "Nazarova", "Saidov"):
        if last in eid:
            await sd.call(A, "POST", f"/api/v1/employees/{eid[last]}/documents", files={"file": (f"shartnoma_{last}.pdf", PDF, "application/pdf")},
                          data={"kind": "contract", "title": f"Mehnat shartnomasi — {last}", "issued_at": str(today - timedelta(days=200))}, label="shartnoma")  # fmt: skip
            await sd.call(A, "POST", f"/api/v1/employees/{eid[last]}/documents", files={"file": (f"pasport_{last}.pdf", PDF, "application/pdf")}, data={"kind": "passport", "title": "Pasport nusxasi"}, label="pasport")

    # E. Prebording: lavozim yo'nalishlari va stajyorlarning avto-yozilishi
    print("E. Prebording")
    await sd.call(hrd, "GET", "/api/v1/preboarding/tracks", label="prebording yo'nalishlari")
    for last in ("Ismoilova", "Abdullayev"):
        try:
            await sd.call(sd.login_of(last), "GET", "/api/v1/preboarding/my", label="stajyor darslari")
        except StopIteration:
            pass

    # F. Topshiriqlar: to'liq bajarilgan, tekshiruvda, jarayonda, muddati o'tgan
    print("F. Topshiriqlar (bajarilganlari bilan)")
    plan = [
        ("Filial 16 kassasini tekshirish", f1, "done", -3), ("Dori qoldig'ini inventarizatsiya qilish", f2, "done", -1),
        ("Yangi narx yorliqlari", f3, "done", -2), ("Sanitariya daftarini to'ldirish", mudir1, "review", 1),
        ("Stajyorlarga mentorlik rejasi", hrm, "in_progress", 4), ("Haftalik savdo hisoboti", mudir1, "todo", 2),
        ("Muddati o'tgan dorilarni ajratish", f2, "in_progress", -1),
    ]
    for title, who, status, days in plan:
        t = await sd.call(hrd, "POST", "/api/v1/tasks", json={"title": title, "description": "Demo topshiriq: bajarilish jarayonini ko'rsatadi", "priority": "high" if days < 2 else "normal", "due_at": (now + timedelta(days=days)).isoformat(), "assignee_id": uid(who)}, label="topshiriq")
        if not t or status == "todo":
            continue
        await sd.call(who, "POST", f"/api/v1/tasks/{t['id']}/accept", label="qabul")
        await sd.call(who, "POST", f"/api/v1/tasks/{t['id']}/move", json={"status": "in_progress"}, label="jarayonda")
        await sd.call(who, "POST", f"/api/v1/tasks/{t['id']}/comments", json={"body": "Boshladim, kun oxirigacha tugataman"}, label="izoh")
        if status in ("review", "done"):
            await sd.call(who, "POST", f"/api/v1/tasks/{t['id']}/move", json={"status": "review"}, label="tekshiruvga")
        if status == "done":
            await sd.call(hrd, "POST", f"/api/v1/tasks/{t['id']}/move", json={"status": "done"}, label="bajarildi")

    # G. Ishdan ketganlar arxivi (tashkiliy tuzilma tahlili va aylanma uchun)
    print("G. Ishdan ketganlar")
    for last, first, months_worked, left_days_ago, reason in [("Karimova", "Nilufar", 14, 40, "own_will"), ("Bakirov", "Islom", 5, 120, "discipline"), ("Sobirova", "Gulchehra", 26, 200, "contract_end")]:
        hired = today - timedelta(days=left_days_ago + months_worked * 30)
        e = await sd.call(A, "POST", "/api/v1/employees", json={"last_name": last, "first_name": first, "department_id": dept["Dorixona tarmog'i"], "position_id": pos.get("Farmasevt"), "branch_id": br.get(16), "hire_date": str(hired)}, label="sobiq xodim")
        if e:
            await sd.call(A, "POST", f"/api/v1/employees/{e['employee']['id']}/dismiss", json={"date": str(today - timedelta(days=left_days_ago)), "reason": reason, "note": "Demo"}, label="ishdan bo'shatish")

    # H. YaQM (yakuniy qimmatli mahsulot): tashkiliy tuzilma sxemasi uchun
    print("H. YaQM")
    dept_yqm = {
        "Rahbariyat": "Strategik rejalar asosida barqaror rivojlanayotgan kompaniya",
        "HR bo'limi": "O'z o'rnida samarali ishlaydigan, sinov muddatidan muvaffaqiyatli o'tgan xodimlar",
        "Dorixona tarmog'i": "Mijozga o'z vaqtida va to'g'ri dori yetkazib bergan, rejani bajargan filiallar",
        "Logistika": "O'z vaqtida va to'liq yetkazilgan yuklar",
        "Omborxona": "Hisobi to'g'ri yuritilgan, muddati o'tmagan tovar qoldig'i",
        "AyTi": "Har bir bo'lim uzluksiz ishlayotgan texnologiyalar asosida ishlashi",
        "Reviziya": "Kamomadsiz, tekshirilgan filiallar",
        "Moliya": "Hisobi yuritilgan va qiymatini yo'qotmaydigan pul mablag'lari",
    }
    for name, text in dept_yqm.items():
        if name in dept:
            await sd.call(A, "PATCH", f"/api/v1/org/departments/{dept[name]}", json={"yqm": text}, label=f"YaQM {name}")
    pos_yqm = {
        "Farmasevt": "Mijozga to'g'ri maslahat bilan sotilgan dori va bajarilgan kunlik reja",
        "Mudir": "Rejani bajargan, kamomadsiz va tartibli filial",
        "Koordinator": "Barcha filiallarda o'z vaqtida bajarilgan standartlar",
        "HR menejer": "Vaqtida yopilgan vakansiyalar va hujjatlari to'liq xodimlar",
        "HR direktor": "Kompaniya uchun harakat qiladigan samarali jamoa",
        "Stajyor": "Sinov muddatidan muvaffaqiyatli o'tgan yangi farmatsevt",
        "Haydovchi": "O'z vaqtida va xavfsiz bajarilgan reyslar",
        "Logistika menejeri": "Kechikishsiz rejalashtirilgan yetkazib berish",
        "Omborchi": "To'g'ri qabul qilingan va jo'natilgan tovarlar",
        "AyTi mutaxassisi": "O'z vaqtida yopilgan texnik so'rovlar",
        "Kassir": "Kamomadsiz kassa va o'z vaqtida topshirilgan tushum",
    }
    for p in positions:
        if p["name"] in pos_yqm:
            await sd.call(A, "PATCH", f"/api/v1/org/positions/{p['id']}", json={"yqm": pos_yqm[p["name"]]}, label=f"YaQM {p['name']}")
