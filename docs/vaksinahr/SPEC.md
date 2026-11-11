# vaksinahr.uz (VAKSINA MED HR v1.5) va hr-profi solishtirmasi

Manba: 2026-11-11 kuni vaksinahr.uz faqat o'qish rejimida ko'rib chiqildi. Hech narsa saqlanmadi, o'chirilmadi va yuborilmadi.
Bu fayl qayta skanerlashga token sarflamaslik uchun yozilgan.
Holat ustuni: ✅ hr-profi'da bor, 🟡 bor, lekin farqi bor, ❌ yo'q.

## Menyu tartibi
hr-profi menyusi shu guruhlar va shu tartibga keltiriladi.

| Guruh | vaksinahr bandi (yo'l) | hr-profi | Holat |
|---|---|---|---|
| ASOSIY | Dashboard (/dashboard) | / (segmentlar: /settings/company) | ✅ |
| ASOSIY | Qabulxona (/resepsion) | /reception | ✅ |
| ASOSIY | Javob olish | /answers | ✅ |
| ASOSIY | Javob olish holati | /answers/holat | ✅ |
| ASOSIY | Tashkiliy tuzilma | /org | ✅ |
| ASOSIY | Reviziya (/reviziya) | /revisions | ✅ |
| ASOSIY | AyTi (/it) | /helpdesk | ✅ |
| DAVOMAT | Davomat (/davomat-face) | /attendance | 🟡 |
| DAVOMAT | Davomat hisobot | /attendance/daily | ✅ |
| DAVOMAT | Davomat QR | /attendance/qr | ✅ |
| DAVOMAT | Smena va filial | /org/rotations | 🟡 |
| DAVOMAT | Cheklist holati | /checklists/status | ✅ |
| DAVOMAT | Tushuntirish xatlari | /letters | ✅ |
| DAVOMAT | Ma'lumotnoma | /hr/references | ✅ |
| DAVOMAT | Jarimalar | /penalties | ✅ |
| MENING ISHIM | Topshiriqlar | /tasks | ✅ |
| MENING ISHIM | Topshiriqlar tahlili | /tasks/analytics | ✅ |
| MENING ISHIM | Eslatmalarim | /reminders | ✅ |
| XODIMLAR | Xodimlar | /employees | ✅ |
| XODIMLAR | Ish o'rinlari | /recruit/vacancies | ✅ |
| XODIMLAR | Nomzodlar | /recruit/candidates | ✅ |
| XODIMLAR | Stajirovkalar | /internship | ✅ |
| XODIMLAR | Arizalar | /recruit/requests | ✅ |
| XODIMLAR | Xodim kerak (/xodim-kerak) | /pharmacy/needs | ✅ |
| MOLIYA | Oylik | /payroll | 🟡 |
| MOLIYA | Oylik hisob | /payroll/sheet | ✅ |
| MOLIYA | Abet | /canteen | ✅ |
| APTEKA TARMOG'I | Aptekalar tarmog'i | /branches | 🟡 |
| APTEKA TARMOG‘I | Mijozlar baholashi | /ratings, /baho/:token | ✅ |
| APTEKA TARMOG'I | Ehtiyoj | /needs | ✅ |
| LOGISTIKA | Dashboard/VHK, Boshqaruv, Live, GPS Davomat, Panel | /logistics | 🟡 |
| OMBORXONA | Omborxona_ish | /warehouse | ✅ |
| TIZIM | Hisobot (/admin/holat) | /attendance/coordinator-report | 🟡 |
| TIZIM | Xodimlar hisoboti | /reports | 🟡 |
| TIZIM | Bo'limlar | /org/departments | ✅ |
| TIZIM | Kirish materiallari | /preboarding | 🟡 |
| TIZIM | Preboarding | /preboarding | ✅ |
| TIZIM | Face ID | /face/admin | ✅ |
| TIZIM | Skaner | /letters (skaner) | 🟡 |
| TIZIM | Qurilmalar | /devices | ✅ |
| TIZIM | Ko'chma davomat, Ko'chma xarita, Jonli kuzatuv | /mobile | 🟡 |
| — | Qo'ng'iroq | /calls | ✅ |

## Sahifalar (asosiy elementlar)

### Dashboard
- Davr tugmalari: Bugun, 7 kun, 30 kun, Oy, Davr. "Yangilash" va "PDF yuklash" tugmalari.
- Segmentlar: 1. Ofis, 2. Dorixona (mudir, farmasevt, stajyor), 3. Hammasi.
- Holat kartalari: Vaqtida, Kech, Kelmagan.
- Bo'limlar ro'yxati: xodim soni, %, kelgan, kech, kelmagan.
- Bloklar:
  - Kunlik taqsimot
  - Davomat ulushi
  - Filiallar/bo'limlar kesimida
  - Top 5 eng intizomli
  - Lavozim/rol bo'yicha
  - Ofis davomati
  - Top 10 kechikuvchilar
  - So'nggi kelishlar (jadval ustunlari: # / Xodim / Bo'lim / Kun / Soat / Vaqt / Holat)
  - Bo'limlar jadvali (bo'lim qidiruvi bilan)

### Qabulxona
- Kartalar: Kelayotganlar, Ofisda hozir, Chiqqanlar, Barcha tashriflar.
- Turlar: Mehmon, Nomzod, Xodim, Murojaat, Posilka.
- Sabablar: Uchrashuv, Hujjat topshirish, Shartnoma/imzo, Konsultatsiya, Yetkazib berish, Shikoyat.
- Forma: ism, telefon, kompaniya, sabab, izoh, kimning oldiga (xodim; sukutda faqat ofis xodimlari), kirish vaqti, kutilayotgan chiqish.
- "Mehmonni qayd etish va xabar" tugmasi xodimga xabar yuboradi.
- Bugungi jurnal filtrlari: Hammasi, Ofisda, Kutilmoqda, Chiqdi, Bekor.

### Javob olish
- Kunlik va soatlik rejim, oy kalendari.
- Tablar: HR kutmoqda, Koordinatorda, Javob berilganlar.
- Amallar: Rad etish, Yakuniy tasdiqlash.

### Javob olish holati
- Excel va PDF eksport.
- Oy kunlari bo'yicha sonlar; xodim kartasi: filial, nechta kunlik, nechta soatlik.
- Qidiruv: xodim yoki izoh bo'yicha.

### Reviziya ✅
- Tablar: Mening filiallarim (sikl, natija, tarix), Vazifalar (bugungi va navbatdagi), Kalendar (oy bo'yicha reja).
- Kartalar: Muddati o'tgan, Sikl o'tkazilgan, Tez orada (14 kundan kam qolgan), Jarayonda (revizor ishlayapti), Rejadagidek, Hali reviziyasiz.
- Qidiruv: filial, mudir, koordinator, revizor yoki javobgar.

### AyTi
- Arizalar ro'yxati, "Yangi ariza" (masalan, "POS ishlamayapti") va izoh, "Arizani yuborish".

### Davomat (shaxsiy)
- Joriy vaqt, "Keladi" va "Ketadi" (rejadagi vaqti bilan).
- Kamera va geolokatsiyaga ruxsat so'raladi.
- "Mening oyligim" vidjeti: Kun, Hafta, Oy.

### Davomat hisobot
- Excel, PDF, "Hisobot yuborish" (Telegramga).
- Kartalar: Jami xodim, Kelgan, Kelmagan, Kechikkan, Dam kuni, Jarima (so'm, qoralama).
- Tablar: Tabel, Tahlil va grafik, Xodimlar jami, Jarimalar.
- Davr: Kun, Hafta, Oy, Davr.
- Guruhlar: Ofis 09:00–18:00, Distribyutsiya, Omborxona (smenalar), Xavfsizlik (sutka).
- Ustunlar: № / F.I.SH. / Lavozim / Holat / Smena-vaqt / Kelish / Ketish / Ishlagan / Kech keldi / Erta keldi / Erta ketdi / Kech ketdi / Raqam.

### Smena va filial
- Tablar: Yangi rotatsiya, Smena o'zgartirish, Monitoring va baza, Tarix, Koordinator ruxsatlari.
- Rotatsiya turlari: Doimiy, Muddatli, Haftalik (tanlangan kunlar), Kunlik.
- Xodim filtri: Hammasi, Farmasevt, Stajyor, Mudir. Filial qidiruvi.
- Smenalar:

| Smena | Turi | Vaqt |
|---|---|---|
| 1-smena | Kunduzgi | 08:00–17:00 |
| 2-smena | Kechki | 17:00–23:59 |
| 1+2 smena | To'liq kun | 08:00–23:59 |
| 2+3 smena | Kechki va tungi | 17:00–07:00 |
| 3-smena | Tungi | 23:00–07:00 |

- Chiqish (ketish) 23:55 gacha qabul qilinadi.
- O'ng tomonda "Yangi rotatsiya xulosasi".

### Cheklist holati (koordinator tashriflari)
- Tablar: Dashboard, Vaqt, Reyting, Tashriflar, Filial qamrovi.
- Filtrlar: koordinator, filial, davr.
- Kartalar: Tashriflar, Filial, Koordinator, O'rtacha ball, Qamrov (masalan 93/147), GPS.
- Ball holati: A'lo ≥85%, O'rtacha 70–84%, Past <70%.
- Bloklar: Javoblar (Ha/Yo'q), Jarayon (GPS bor, GPS yo'q, kiritilmagan filial), Kunlik tashriflar (14 kun), Ball taqsimoti.
- Qoida: har filialga oyiga 4 tagacha tashrif.

### Tushuntirish xatlari
- Segmentlar: Dorixona va Ofis xodimlari.
- Kartalar: Jami, Imzo kutilmoqda, Qaror kutilmoqda, Tasdiqlangan, Bekor qilingan.
- Telegram hisobot har 3 kunda soat 10:00 da yuboriladi; Excel va "Hozir yuborish" tugmalari.
- "Hujjatni tekshirish": QR skaner yoki hujjat raqami.
- Bosqichlar:
  1. Tushuntirish xati
  2. Oylikdan jarima
  3. Ishdan ozod etish
- Tasdiqlashda keyingi holatga o'tiladi, bekor qilishda bosqich oshmaydi.
- Filtrlar: Kechikish, Kelmagan.
- Tizim skaneri: kelgan PDF lar.

### Ma'lumotnoma
- Shapka sozlamasi: kompaniya nomi, rahbar lavozimi, direktor F.I.Sh.
- Xodim qidiruvi va tanlangan xodim kartasi.
- So'nggi yaratilganlar: Ko'rish, PDF, Bekor qilish, O'chirish.
- 1 varaqli A4 PDF: logo, filial, lavozim, smena va QR.

### Jarimalar
- Segmentlar: Dorixona va Ofis. Filtrlar: Hammasi, Kechikkan, Kelmagan. Excel va PDF.

### Topshiriqlar
- Kartalar: Jami, Kechikkan, Bugun, Jarayonda, Tekshiruvda, Bajarilgan.
- Filtrlar: bo'lim, ustuvorlik, sana, Shoshilinch.

### Topshiriqlar tahlili
- Kartalar: Yangi, Jarayonda, Bajarilgan, Kechikkan, Bugun muddati, Xavf ostida (3 kun ichida), Tasdiqni kutmoqda.
- Grafiklar: dinamika, deadline monitoring, kalendar, prioritetlar, topshiriq turlari, manbalar.
- Ro'yxatlar: Top xodimlar, Eng muammoli xodimlar, So'nggi faoliyat.

### Eslatmalarim
- Kartalar: Bajarilmagan, Bugun, Kelgusi 7 kun, Bajarilgan, Menga biriktirilgan.
- Ko'rinishlar: Kanban, Ro'yxat, Taqvim. Tablar: Mening, Boshqa, Arxiv.

### Xodimlar
- Tugmalar: Xodim qo'shish, Login Excel, Excel, PDF.
- Kartalar: Jami, Ishlayapti, Ta'tilda, Bo'shatilgan.
- Ustunlar: № / Rasm / F.I.Sh. / Lavozim / Rol / Bo'lim / Holat / Smena / Ishga olingan.

### Ish o'rinlari va Nomzodlar
- Ish o'rinlari: "Yangi ish o'rni", "Ish o'rnini yopish".
- Nomzodlar ustunlari: Nomzod / Ish o'rni / Aloqa / Holat / Rekruter.

### Stajirovkalar
- Holatlar: Jarayonda, Tayyor, Ishga olingan.

### Arizalar (zayafkalar)
- Holatlar: Ochiq, Yangi, Ko'rib chiqilmoqda, Qabul qilingan, E'lon qilingan, Yopilgan.
- Ustunlar: ID / Bo'lim-lavozim / Ariza bergan / Soni / Prioritet / Status / Mas'ul / HR yuborgan / Rekruter qabul / E'lon tasdiqlangan.

### Xodim kerak (hr-profi: /pharmacy/needs)
- Filial bo'yicha xodim so'rovi.
- Holatlar: Qidirilmoqda, Topilgan, Rad etilgan. Amallar: Topildi, Rad etish.

### Oylik
- Intizom nazorati: Bloklangan, Ruxsat berilgan; Intizom PDF.
- Tushuntirish xatlari bosqichlari shu sahifada ham ko'rinadi.

### Oylik hisob
Savdo rejasiga asoslangan hisob. Ustunlar:
- Asosiy: № / Xodim / Lavozim / Telefon.
- Reja va savdo: Joriy reja / Oldingi reja / Haqiqiy savdo / Rejadan ortiq / Reja % / Savdo foizi / Foiz summasi.
- Maosh va bonuslar: Fiks maosh / Reja bonusi / KPI bonus / Avans / Qayta hisob.
- Jarimalar: Vaqt jarimasi / Muddat jarimasi.
- Natija: Hisoblangan / Qo'lga-karta.
- Tugmalar: Tasdiqlash, Excel.

### Abet
- Bugungi menyu; tablar: Baholash, Tahlil, QR kod.

### Aptekalar tarmog'i
- Filtrlar: koordinator, smena; Jamoa bor/yo'q, Mudir yo'q.
- Filial kartasi: "Batafsil"; "Xodim kerak" bloki.

### Mijozlar baholashi ✅
- Har filial uchun QR (A4 PDF); tablar: QR kodlar, Xodim baholari, Dorixona baholari, Statistika.
- Ustunlar: № / Filial / Mudir / Holat / Versiya / Amallar (Ko'rish, A4 PDF, Almashtirish, O'chirish, Yaratish).

### Ehtiyoj
- Holatlar: Tasdiq kutmoqda, Jarayonda, Yakuniy tasdiq, Yakunlangan, Tarix.
- "Batafsil: kim va qachon"; amallar: Tasdiqlash, Bekor qilish.

### Logistika
Tashqi tizim iframe'da ochiladi: Dashboard/VHK, Boshqaruv, Live, GPS Davomat, Panel.

### Omborxona_ish
- Tablar: Ish, Grafik, Xodim, Holat.

### Hisobot (/admin/holat)
- Koordinator tanlash; davr: Bugun, 7, 30, 90 kun; PDF va Excel.

### Xodimlar hisoboti
- 4 qadam:
  1. Filial yoki xodim bo'yicha tanlash
  2. Filial va xodimlar
  3. Davr
  4. Holatlar: Kelgan, Kechikkan, Kelmagan, Chala kun, Ta'til, Hali kelmagan, Dam kuni
- "Hisobot olish" tugmasi.

### Bo'limlar
- Umumiy lavozimlar (hech qaysi bo'limga bog'lanmagan).
- Bo'lim kartasi: boshliq va lavozimlar soni. Tugmalar: Yangi bo'lim, Yangi lavozim.

### Kirish materiallari
- 8 ta dars: video (YouTube/Drive), slayd va test savollari.
- Kim ko'radi: Hamma, Faqat o'quvchilar, Faqat xodim/stajyorlar.

### Preboarding
- Rol bo'yicha (Farmasevt, Mudir), 5 bosqich: video, slayd, savollar; Qoralama.

### Qurilmalar ✅
- Tablar: Ruxsat so'rovlari, Qurilmalar, Majburiy xodimlar, Sozlamalar, Login tarixi, Xavfsizlik hodisalari.

### Ko'chma davomat, xarita va jonli kuzatuv
- Xodim: ruxsat, tracking, bugun.
- Xarita: kim ishda. Jonli ro'yxat: Online, Offline.

## Qolgan ishlar (navbat)
1. ✅ Menyu vaksinahr tartibiga keltirildi (nav.ts LAYOUT).
2. ✅ Reviziya, Mijozlar baholashi va Qurilmalar qurildi.
3. 🟡 bandlar: Dashboard segmentlari (Ofis/Dorixona), Oylik hisobning savdo rejasi ustunlari, Cheklist holati tablari, Davomat hisobotining segment va ustunlari.
