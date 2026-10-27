# VaksinaHR

HR va operatsion boshqaruv tizimi. Reja: [PLAN.md](PLAN.md). Hozirgi holat: **F0-F40 tayyor** (v1.1.0) (poydevor, auth/rollar, bildirishnomalar/realtime/Telegram, tashkiliy tuzilma, xodimlar, smena va grafik, davomat, Face ID, davomat tahlili, javob olish, tushuntirish xatlari, jarimalar, topshiriqlar, eslatmalar, apteka tarmog'i).

## Tuzilma

```
core/backend      FastAPI (SQLAlchemy async, Alembic, arq worker)
core/frontend     React + Vite + TS + Tailwind
clients/<nom>     mijozga xos: client.yaml, backend_ext/, frontend_ext/, migrations/
deploy/           nginx gateway, db image, host nginx namunasi, skriptlar
docker-compose.yml, docker-compose.dev.yml, Makefile
```

## Ishga tushirish

```bash
make dev      # lokal ishlab chiqish (hot reload), http://localhost:6788
make up       # production-ga yaqin (127.0.0.1:6788)
make smoke    # gateway orqali tekshiruv
make test     # backend: ruff + pytest (docker ichida)
make lint     # frontend: oxlint + tsc
make admin LOGIN=admin NAME="Ism Familiya"   # birinchi Ta'sischi (parol bir marta chiqadi)
```

Tashqariga faqat **6788** (gateway) chiqadi. Qolgan servislar (api, db (Postgres+pgvector), redis, minio, worker) ichki tarmoqda.
`.env` ni `make init` tasodifiy sirlar bilan yaratadi.

## UI qoidalari

- **Yaratish va tahrirlash har doim alohida sahifada** (`/<resurs>/new`, `/<resurs>/:id/edit`). Modal ham, drawer ham ishlatilmaydi.
  Forma sahifasi: `PageHeader` (orqaga + sarlavha), `FormSection` kartalari, pastda yopishqoq `FormFooter` (Bekor qilish / Saqlash),
  saqlangach ro'yxatga qaytish + toast. Sub-resurslar (masalan lavozimlar) ota sahifada bo'lim sifatida.
- Natija sahifalari (yaratilgan foydalanuvchining vaqtinchalik paroli) va ommaviy amallar (CSV import) ham alohida sahifa.
- Faqat halokatli amallarni (o'chirish, parolni tiklash, bloklash) tasdiqlash uchun `useConfirm()` kichik dialogi ishlatiladi.

## Autentifikatsiya va rollar (F1)

- Login/parol (argon2), JWT access (15 daqiqa, httpOnly cookie) + aylantiriladigan refresh token (30 kun, DB da faqat hash).
  Eski refresh token qayta ishlatilsa sessiya yopiladi. Kirishda 5 xato -> 15 daqiqa blok (Redis).
- Cookie asosidagi CSRF himoyasi: o'zgartiruvchi `/api` so'rovlarida `X-Requested-With` header shart (frontend o'zi qo'shadi).
- Rollar va ruxsatlar DB da (mijoz o'zgartira oladi). Ruxsat: `users.read`, wildcard `users.*`, `*`.
  Privilege escalation yo'q: faqat o'zingizdagi ruxsatlarni/rollarni bera olasiz. Oxirgi Ta'sischi o'chirilmaydi.
- Yangi foydalanuvchi: login ismdan avto (`tursunboyev.orifjon`, Kirill ham), vaqtinchalik parol bir marta ko'rsatiladi,
  birinchi kirishda almashtirish majburiy.
- Audit jurnali: kirish/chiqish, foydalanuvchi va rol o'zgarishlari (parollar yozilmaydi).
- Mijoz extension o'z ruxsatlarini `app.rbac.register_permission(...)` bilan qo'shadi.

## Bildirishnomalar, realtime, Telegram (F2)

- `notify(db, [user_ids], "kind", params=...)` + `deliver(app, notes)` (commitdan keyin): bazaga yozadi, WebSocket orqali
  darhol yetkazadi (Redis pub/sub, ko'p jarayonda ham ishlaydi) va Telegram navbatiga qo'yadi. Shablonlar ikki tilda:
  `register_template(...)` (extension ham qo'sha oladi).
- WebSocket: `/ws/notifications` (cookie auth, Origin tekshiruvi, 45s jimlikda sessiya qayta tekshiriladi, mijoz avto-qayta ulanadi).
- Telegram: `.env` da `TELEGRAM_BOT_TOKEN`. Foydalanuvchi Profil -> Telegram orqali ulaydi (bir martalik kod, 10 daqiqa).
  `bot` servisi (long polling) buyruqlarni qabul qiladi (`/start`, `/stop`, `/status`), yuborishni `worker` bajaradi
  (qayta urinish, bot bloklansa avtomatik uzish). Token bo'lmasa Telegram o'chiq, tizim bunsiz ishlaydi.
- Xodimlarga xabar yuborish: `notifications.send` ruxsati (Bildirishnomalar sahifasida).

## Tashkiliy tuzilma (F3)

- **Bo'limlar** daraxti (eng ko'pi 6 daraja, tsikl va bir xil nom tekshiriladi), **lavozimlar** (bo'lim ichida yoki umumiy),
  bo'lim **boshlig'i** (faol foydalanuvchi; tayinlanganda unga bildirishnoma boradi). Yangi bo'limga standart lavozimlar
  avtomatik yaratiladi: `client.yaml -> settings.org.default_positions`.
- **Filiallar**: raqam, manzil, tuman, mudir, koordinator, **joylashuv (lat/lng) va geofence radiusi** (standart 100 m),
  xarita ko'rinishi, CSV import (raqam bo'yicha yangilaydi, xato bo'lsa hech narsa saqlamaydi).
  `app/geo.py`: `haversine_m`, `within_radius` (davomat geofence F6 da ishlatiladi; PostGIS kerak emas).
- Xarita tile manbasi: standart OpenStreetMap. Productionda o'zimizning PMTiles ga o'tkazish kerak (OSM siyosati og'ir
  yuklamaga mos emas): `client.yaml -> settings.map.tiles: ["https://.../{z}/{x}/{y}.png"]`.
- Ruxsatlar: `org.read|manage`, `branches.read|manage`. Yangi default ruxsatlar mavjud rollarga bir marta beriladi
  (`app_meta` da yoziladi), administrator olib tashlagani qaytarilmaydi.
- Lokal sinov uchun namunaviy ma'lumot: `docker compose exec api python -m app.cli seed-demo-org`.

## Xodimlar (F4)

- **Xodim kartasi**: shaxsiy ma'lumot, PINFL/pasport (faqat `employees.sensitive` ko'radi, boshqalarga maskalanadi), bo'lim/lavozim/filial,
  rasm va hujjatlar (MinIO, API orqali; turi magic bytes bilan tekshiriladi, muddati kuzatiladi). Kirish hisobi ixtiyoriy
  (xodimdan avtomatik login+vaqtinchalik parol yoki mavjud foydalanuvchini ulash).
- **Ish tarixi**: ishga olish, o'tkazish (kuchga kirish sanasi bilan), bo'shatish, tiklash, birlashtirish avtomatik yoziladi. Xodim o'chirilmaydi, bo'shatiladi.
  Bo'shatilganda kirish hisobi bloklanadi va sessiyalari yopiladi.
- **Dublikat nazorati**: PINFL/pasport bir xil bo'lsa rad etiladi; telefon yoki ism+tug'ilgan sana bir xil bo'lsa ogohlantirib tasdiq so'raydi.
  Dublikatlar sahifasi va birlashtirish (hujjat/tarix ko'chadi, bo'sh maydonlar to'ldiriladi).
- **Excel/CSV**: shablon, import (avval tekshirish: xato va dublikat qatorlar o'tkazib yuboriladi), eksport (sezgir ustunlar faqat ruxsatlilarga).
- **Ommaviy amallar**: o'tkazish, bo'shatish, tiklash, hisob yaratish (loginlarni CSV ga yuklab olish). Har xodim alohida bajariladi.
- Ruxsatlar: `employees.read|sensitive|create|update|transfer|dismiss|documents|export|import|merge|accounts`.

## Smena va grafik (F5)

- **Smena turlari**: qat'iy (vaqti belgilangan, kechikish hisoblanadi) va erkin (kechikish hisoblanmaydi); tungi smena (tugash <= boshlanish
  keyingi kunga o'tadi) va 24 soatlik (teng vaqt); tanaffus, kechikish/erta ketish imtiyozi, minimal ish vaqti.
- **Ish guruhlari** (ofis, dorixona, ombor, qo'riqlash, boshqa): standart smena, haftalik dam kunlari, bayramga amal qilish, davomat shartligi.
  Bitta guruh standart; guruhi belgilanmagan xodim shu guruh qoidasiga amal qiladi.
- **Kunni aniqlash ustuvorligi**: qo'lda yozilgan grafik > bayram (agar guruh bayramga amal qilsa; ko'chirilgan ish kuni haftalik damni bekor qiladi)
  > haftalik dam > guruhning standart smenasi.
- **Bayramlar**: aniq yil yoki har yili; O'zbekistonning qat'iy sanali bayramlarini bir bosishda qo'shish. Hayit kabi harakatlanuvchilar qo'lda kiritiladi.
- **Grafik tuzish**: xodim/guruh/bo'lim/filial bo'yicha, sana oralig'i va hafta kunlari, smena yoki dam yoki shablon (2/2, sutka-uch; xodimlarni
  siklda siljitish) yoki tozalash. Avval ko'rib chiqish (dry run), keyin qo'llash. Oylik jadval (`/schedule`) va xodim oylik taqvimi.
- Demo ma'lumot (faqat lokal): `docker compose exec api python -m app.cli seed-demo-schedule` (vaqtlar taxminiy, mijoz o'zgartiradi).
- Ruxsatlar: `schedule.read` (ko'rish), `schedule.edit` (grafik tuzish), `schedule.manage` (smena/guruh/shablon/bayram).

## Davomat (F6)

- **Keldi/ketdi**: xodim `/attendance` da GPS orqali, yoki telefon kamerasi bilan filial QR kodini skanerlab (`/attendance/punch?t=...`) belgilaydi.
  Ochiq yozuv bo'lsa ketish, bo'lmasa kelish hisoblanadi. Bir daqiqada ikki marta belgilab bo'lmaydi.
- **QR**: `/attendance/qr` filial ekranida ochiladi; kod HMAC bilan imzolangan va har daqiqa yangilanadi (1-2 daqiqa amal qiladi), shuning uchun
  rasmini yuborib bo'lmaydi. "Barcha QR larni bekor qilish" eski kodlarni o'chiradi. QR bilan ham filial geofence'i tekshiriladi (koordinata kiritilgan bo'lsa).
- **Geofence**: filial radiusidan tashqarida yoki GPS aniqligi 150 m dan yomon bo'lsa rad etiladi. Filialda koordinata yo'q bo'lsa GPS orqali belgilab bo'lmaydi.
- **Smena aniqlash**: grafikdan (F5) hozirgi vaqtga mos smena olinadi (boshlanishdan 3 soat oldin, tugagandan 3 soat keyingacha); tungi smenada ketish
  keyingi kunda ham shu smenaga yoziladi. Grafiksiz kunda belgilash mumkin ("Grafiksiz keldi").
- **Kechikish/erta ketish**: faqat kechikish kuzatiladigan (qat'iy) smenada; imtiyozdan oshsa smena vaqtidan boshlab hisoblanadi. Ishlagan vaqtdan tanaffus ayriladi.
  Smena vaqti yozuvga muhrlanadi, keyin smena o'zgarsa ham tarix buzilmaydi.
- **Kun holatlari**: keldi, kech, erta, ishda, ketish belgilanmagan, kam ishladi (erkin smena), kelmagan, dam, bayram, kutilmoqda, davomat shart emas.
  "Kelmagan" faqat smena tugagach yoki o'tgan kunlar uchun.
- **Hisobotlar**: kunlik davomat (`/attendance/daily`), hafta/oy tabeli va jami ko'rsatkichlar (`/attendance/timesheet`), Excel eksport, xodim oylik yozuvlari.
- **Qo'lda tuzatish**: yozuv qo'shish/o'zgartirish/o'chirish faqat sabab bilan; oldin/keyin holati `attendance_corrections` va audit jurnaliga yoziladi.
- Vaqt mintaqasi: `TIMEZONE` (standart Asia/Tashkent). Frontend vaqt kiritishda UTC+5 deb oladi (O'zbekistonda yozgi vaqt yo'q).
- Ruxsatlar: `attendance.punch` (barcha xodim rollari), `attendance.read`, `attendance.edit`, `attendance.qr` (HR, mudir).

## Apteka tarmog'i (F14)

- **Tarmoq holati** (`/pharmacy`): har filial uchun jamoa (mudir/farmasevt/stajyor) me'yor bilan (masalan F 1/2), bugungi davomat (hozir ishda/kutilgan, kech, kelmagan, ruxsatli) va holat:
  **hech kim yo'q** (ish vaqtida yopilmagan yozuvli xodim yo'q), **me'yordan kam**, **joyida**. Tepada KPI; filtr: tuman, holat, qidiruv. Koordinator/mudir faqat o'z filiallarini ko'radi (`pharmacy.own`).
- **Lavozim turi** lavozim nomidagi kalit so'zlardan aniqlanadi: mudir/заведующий, farmasevt/provizor/фармацевт, stajyor/стажёр (stajyor farmasevtdan ustun). Filial mudiri
  (`manager_user_id`) bilan bog'liq xodim ham mudir hisoblanadi. Lavozimlarni shunday nomlang.
- **Filial kartasi** (`/pharmacy/:id`): bugungi holat, me'yor, jamoa (kelish vaqti, kechikish, holat), keyingi 7 kunlik grafik qamrovi (mudir/farmasevt yo'q kun qizil), ochiq so'rovlar, xarita.
  Me'yor va ish vaqti `/pharmacy/:id/edit` da; **ommaviy me'yor** `/pharmacy/norms` da (hamma yoki faqat belgilanmaganlarga, oldin ko'rib chiqish bilan).
- **Ommaviy xarita** (`/pharmacy/map`): rang = holat, belgini bossangiz karta ochiladi.
- **Xodim kerak** (`/pharmacy/needs`): filial, lavozim, soni, shoshilinchlik, qachondan, sabab. Koordinator/mudir o'z filialiga yaratadi; HR va filial koordinatoriga bildirishnoma.
  HR "bajarildi" qiladi (yaratuvchiga xabar), yaratuvchi izoh bilan bekor qila oladi. Me'yordan kam filiallar uchun bir bosishda so'rov taklifi. (F17 da vakansiyaga ulanadi.)
- **Ma'lumot sifati** (`/pharmacy/quality`): mudir, koordinator, joylashuv, me'yor, ish vaqti, telefon, manzil yo'q va xodimsiz filiallar ro'yxati: 142 ta filial ma'lumotini bir joyda tekshirish uchun.
  Filiallarni ommaviy kiritish: F3 dagi CSV import (`/branches/import`), keyin ommaviy me'yor.
- Ruxsatlar: `pharmacy.read` (hammasi), `pharmacy.own` (o'z filiallari), `pharmacy.request`, `pharmacy.manage`.

## Eslatmalar (F13)

- **Eslatma** (`/reminders`): sarlavha, izoh, ixtiyoriy ichki havola (bildirishnomani bosganda shu sahifa ochiladi, masalan topshiriqdagi "Eslatma qo'yish" tugmasi), vaqt (Toshkent).
  **Takrorlanish**: bir martalik, har N kun / hafta (kunlar tanlanadi) / oy (31-sana qisqa oylarda oy oxiriga tushadi) / yil (29-fevral kabisa bo'lmagan yilda 28), "shu sanagacha" (kiritilgan).
  Formada keyingi 5 ta vaqt oldindan ko'rsatiladi.
- **Yuborish**: worker har daqiqada vaqti kelganlarni ilova ichida (realtime) va, tanlangan bo'lsa, Telegramga yuboradi. Aniqlik ±1 daqiqa (bir daqiqalik tekshiruv; haqiqiy stekda sinab ko'rildi:
  07:08:46 ga qo'yilgani 07:09:00 da keldi). Worker to'xtab qolsa, o'tib ketgan takrorlar yig'ilmaydi: bir marta yuboriladi va keyingi vaqtga o'tadi.
- **Boshqarish**: kechiktirish (10 daqiqa, 1 soat, ertaga 09:00; asosiy jadval o'zgarmaydi), "Bajarildi", to'xtatish/davom ettirish (to'xtatilgan paytda o'tganlar yig'ilmaydi), tahrirlash, o'chirish, tarix.
  Yaqin 7 kunlik jadval (takrorlar yoyilgan). Bir foydalanuvchida 200 tagacha faol eslatma.
- **Boshqalarga**: `reminders.assign` (topshiriq bera oladigan rollar) boshqa xodimlarni oluvchi qilib qo'sha oladi; oluvchi ko'radi, kechiktiradi va belgilaydi, lekin tahrirlay/o'chira olmaydi.
- Ruxsatlar: `reminders.own` (hamma rollar), `reminders.assign`.

## Interfeys dizayni (F31: qayta qurilgan UI)

- **Uslub:** neytral palitra (iliq kulrang kanvas, oq kartalar, chegarasiz yumshoq sirtlar), asosiy amal rangi "siyoh" (qora; dark da oq), bitta yashil urg'u (ijobiy/diagramma). Shrift **Geist** (matn) va **Geist Mono** (KPI raqamlari), jadvalda tabular raqamlar. Tokenlar: `core/frontend/src/styles/tokens.css`. Mijoz brendi (`brand.primary`) standart qora bo'lmasa qo'llanadi va dark da avtomatik yorqinlashtiriladi.
- **Yon panel:** bo'limlar yig'iladigan (accordion), joriy sahifa bo'limi o'zi ochiladi, holat saqlanadi; "rail" (faqat ikonkalar) rejimi; belgilar (hisoblagichlar) saqlangan.
- **Filtrlar** endi bir qatorda (ilgari `w-full` va `w-auto` to'qnashuvi sabab har biri alohida qatorga tushardi: `tailwind-merge` bilan hal qilindi, `lib/cn.ts`).
- **Parol maydonlari** hammasida ko'zcha (ko'rsatish/yashirish): `PasswordInput`.
- **Kursor:** bosiladigan hamma element (select, dropdown elementlari, label, checkbox, fayl tanlash, menyu) `cursor: pointer`, o'chirilgani `not-allowed`. Select'lar o'z chevroni bilan, hover/active/focus holatlari, klaviatura fokus halqasi, "skip to content".
- Funksiya va marshrutlar o'zgarmagan: faqat ko'rinish.

## Xavfsizlik va chiqarish (F30)

- **Xavfsizlik:** [docs/SECURITY.md](docs/SECURITY.md) — pentest checklist (OWASP bo'yicha) va har bandning tekshiruvi. Avtomatik testlar (`tests/test_security.py`): **300+ endpointning hammasi tokensiz 401/403** (OpenAPI dan supurish: yangi endpoint avtomatik qamraladi), hamma o'zgartiruvchi endpoint CSRF headerni talab qiladi, cookie bayroqlari, chastota cheklovi, Excel/CSV **formula injection** himoyasi, injection satrlari, production sozlama tekshiruvi, metrikalar yopiqligi.
- **Chastota cheklovi:** nginx (IP bo'yicha) + ilova (Redis, qoidalar: auth, AI, qidiruv, eksport, yuklash, umumiy) + login qulfi. Gateway mijoz IP sini soxtalashtirib bo'lmaydigan qilib uzatadi. CSP va xavfsiz sarlavhalar; `/api/docs` productionda yopiq.
- **Production tekshiruvi:** zaif sir bilan API ishga tushmaydi; `make doctor` — `.env`, tarmoq, xizmatlar, zaxira yoshi, TLS muddati (✘/⚠).
- **Monitoring:** `/api/health/ready`, Prometheus metrikalari (`/api/metrics`, ichki), ixtiyoriy `--profile monitoring` (Prometheus + Grafana + ogohlantirish qoidalari), `deploy/scripts/watchdog.sh` (cron, muammoda Telegramga bir marta xabar va "tiklandi"). [docs/RUNBOOK.md](docs/RUNBOOK.md): kundalik ishlar, muammolar jadvali, sirlarni almashtirish.
- **Yuk testi:** `make loadtest` (alohida baza va konteyner); 60 parallel faol foydalanuvchi, 2000 xodim: ~240 RPS, p95 0.7–1.0 s, **0% xato** ([docs/LOADTEST.md](docs/LOADTEST.md)). API endi `WEB_CONCURRENCY=3` jarayonda ishlaydi (metrikalar Redis da yig'iladi).
- **Tiklash mashqi:** yangi serverga to'liq tiklash: 93 jadvalning hammasi, parol hashlari va 63 fayl mos, tiklash 10 s ([docs/BACKUP.md](docs/BACKUP.md)).
- **Chiqarish:** [docs/RELEASE.md](docs/RELEASE.md) — darvoza ro'yxati va go-live tartibi. Versiya **1.0.0**.
- **Ma'lum cheklovlar:** MFA yo'q; mustaqil (tashqi) pentest o'tkazilmagan; yuk testi lokal mashinada olingan (productionga o'xshash serverda takrorlash tavsiya etiladi).

## Eski tizimdan migratsiya (F29)

- **`/migration`** (ruxsat `migration.manage`): fayl (CSV/Excel) → ustunlarni moslashtirish (avtomatik taklif + saqlanadigan **shablonlar**) → **dry-run** → import → (kerak bo'lsa) **orqaga qaytarish**. To'liq qo'llanma: [docs/MIGRATION.md](docs/MIGRATION.md).
- Ikki tur: **xodimlar** (eski ID saqlanadi; bor xodim yaratilmaydi, lekin eski ID si bog'lanadi; bo'shatilganlar tarixi bilan; yo'q bo'lim/lavozim/filiallarni yaratish ixtiyoriy) va **davomat tarixi** (xodim eski ID/tabel/PINFL/telefon bo'yicha; tungi smena; bor kunlar o'tkaziladi; faylga ko'ra soat bazadagi soat bilan solishtiriladi).
- Dry-run import kodining o'zini tranzaksiyada bajarib bekor qiladi: tekshiruvdan o'tgan import ham o'tadi. Har yozuv paket raqamini oladi; asl fayl MinIO da, hamma amal auditda.
- **Solishtirish** (`/migration/reconcile`): eski tizimdan olingan nazorat summalari (xodimlar soni, oy bo'yicha davomat yozuvlari va soatlar, filial kesimida) yangi tizim raqamlari bilan jonli solishtiriladi: eski / yangi / farq / mos (ruxsat etilgan farq bilan). CSV dan ommaviy yuklash mumkin.
- **Cheklov:** haqiqiy eski tizim fayli bilan sinalmagan; birinchi faylni staging nusxada dry-run qiling.

## Mijoz paketi (F28)

Yangi mijoz ~1 soatda ko'tariladi: **[docs/NEW-CLIENT.md](docs/NEW-CLIENT.md)** (qadamlar va tekshiruv ro'yxati).

```bash
deploy/scripts/new-client.sh acme "Acme HR" --domain hr.acme.uz --node-ip <IP> --off logistics --env
make up && make admin && make smoke
```

- **client.yaml sxemasi:** [docs/CLIENT-YAML.md](docs/CLIENT-YAML.md), JSON Schema `clients/client.schema.json`, tekshirish `make validate-client CLIENT=acme`.
- **Extension (kod, sahifa, hodisa, jadval):** [docs/EXTENSIONS.md](docs/EXTENSIONS.md); toza skelet `clients/_template`, ishlaydigan namuna `clients/example`.
- **Zaxira/tiklash:** [docs/BACKUP.md](docs/BACKUP.md): `make backup`, `make verify-backup FILE=...` (ishlayotgan bazaga tegmaydi), `make restore FILE=...`; shifrlash va S3 nusxa.
- **Yangilash:** [docs/UPGRADE.md](docs/UPGRADE.md): `make upgrade TAG=vX.Y.Z` (zaxira → kod → build → migratsiya → tekshiruv), qaytarish tartibi. O'zgarishlar: [CHANGELOG.md](CHANGELOG.md).
- **Sinov (F28):** ayrim papkada yangi mijoz (`smoke1`: boshqa brend, 2 modul o'chirilgan, alohida portlar) noldan 53 soniyada (kesh bilan) ko'tarildi; admin yaratildi, `/api/v1/meta` da brend va modullar to'g'ri; zaxira olindi, foydalanuvchi o'chirildi, tiklashdan keyin qaytdi.

## Hisobotlar markazi (F27)

- **Hisobot katalogi** (`/reports`): davomat (filiallar kesimida), xodimlar soni, topshiriqlar, ehtiyojlar, AyTi ticketlar, mehmonlar. Har tur o'z ruxsati bilan (masalan davomat — `attendance.read`), foydalanuvchi faqat o'ziga ruxsat etilganini ko'radi. Davr (hafta / oy / o'tgan oy / oraliq, 62 kungacha), format **Excel yoki PDF** (PDF da kirill va o'zbek harflari), til UZ/RU. Raqamlar tegishli modul tahlili bilan bir manbadan hisoblanadi.
- **Tarix** (`/reports/history`): tuzilgan va sizga yuborilgan hisobotlar; fayl MinIO da 90 kun saqlanadi, keyin avtomatik o'chadi. Yuklab olish auditga yoziladi; faylni faqat tuzgan, qabul qiluvchi va `reports.manage` ko'radi.
- **Jadvalli hisobotlar** (`/reports/schedules`, yaratish va tahrirlash alohida sahifada): har kuni / hafta kuni / oy kuni (1–28) va vaqt (Asia/Tashkent), davr nisbiy (kecha, oxirgi 7 kun, o'tgan hafta, shu oy, o'tgan oy), qabul qiluvchilar va kanal: **ilova ichida** bildirishnoma va/yoki **Telegram** (fayl hujjat sifatida; Telegram ulanmaganlarga faqat ilova). "Hozir ishga tushirish" jadvaldan tashqari darhol yuboradi.
- **Ishonchlilik:** worker `report_scheduler` har daqiqada muddati kelganlarni ishga tushiradi (qayta ishga tushganda o'tkazib yuborilganlar bir marta bajariladi, takrorlanmaydi); bitta hisobot xatosi boshqalarni to'xtatmaydi: xato `failed` bo'lib tarixga yoziladi va jadval egasiga xabar boradi.
- Ruxsatlar: `reports.read` (direktor, HR menejer), `reports.manage` (HR direktor: jadvallar va butun tarix).
- **Cheklov:** Telegramga fayl yuborish haqiqiy bot tokeni bilan lokalda sinalmadi (testlarda navbatga qo'yilishi tekshirilgan).

## AI va qidiruv (F26)

- **Global qidiruv:** yuqoridagi qidiruv maydoni (Enter) → `/search?q=...`. Xodimlar, filiallar, nomzod/vakansiyalar, topshiriqlar, ehtiyojlar, AyTi ticketlar, mehmonlar, mashinalar va qo'ng'iroqlar bitta so'rovda, **faqat foydalanuvchi ko'ra oladiganlari** (xodim o'z topshiriq/ticketlarini, HR/direktor hammasini). Har guruhdan 6 tagacha; `%`/`_` belgilar literal; ism/sarlavha uchun trigram indekslar.
- **AI (Claude API):** `.env` da `ANTHROPIC_API_KEY` bo'lsagina ishlaydi, bo'lmasa tizim bunsiz (qoidalar asosida) davom etadi. Backend to'g'ridan-to'g'ri Messages API ga murojaat qiladi (SDK shart emas), model `/ai/settings` da (standart `claude-haiku-5-5`).
  - **AI xulosa:** ticket, ehtiyoj, topshiriq va nomzod sahifasida "Xulosa qilish" (3–5 jumla, UZ/RU). Natija keshlanadi, matn o'zgarsa yangilanadi. **Ichki izohlar va nomzod ismi modelga yuborilmaydi**; ko'rish huquqi tekshiriladi.
  - **Rezyume tahlili:** `POST /recruit/candidates/parse` endi Claude'dan foydalanadi (telefon/email/sana tekshirib normallashtiriladi, noto'g'ri qiymat tashlanadi); AI o'chiq/xato/limit bo'lsa avvalgi qoidalar ishlaydi (`engine: rules`).
  - **Ticket avto-to'ldirish:** yangi ticket formasida "AI bilan to'ldirish" sarlavha, kategoriya va ustuvorlikni taklif qiladi (foydalanuvchi tekshirib saqlaydi).
- **Xavfsizlik va nazorat:** foydalanuvchi matni `<data>` ichida "ma'lumot" sifatida beriladi (ichidagi ko'rsatmalarga amal qilinmaydi). Har so'rov token hisobi bilan yoziladi (matn saqlanmaydi): `/ai/usage` (kimdan, qaysi funksiya, xatolar). `/ai/settings` (alohida sahifa): yoqish/o'chirish, model, kunlik limit (foydalanuvchiga), funksiyalarni alohida o'chirish; o'zgarish auditda. Ruxsatlar: `ai.use` (hamma rol), `ai.manage` (HR direktor).
- **Cheklov:** haqiqiy Claude API chaqiruvi lokalda sinalmadi (kalit yo'q); mantiq testlarda model javobi almashtirilib tekshirilgan. Kalit qo'yilgach `/ai/usage` da birinchi so'rovlarni kuzating.

## Qo'ng'iroqlar (F25)

- **LiveKit** (o'z serverimizda, `livekit` konteyneri): audio/video, konferensiya (50 tagacha), ekran ulashish. Brauzer `/livekit` (gateway orqali WebSocket) ga ulanadi; media to'g'ridan-to'g'ri **7881/tcp** (fallback) va **7882/udp** orqali o'tadi. Productionda `.env` da `LIVEKIT_NODE_IP` = serverning ochiq IP si bo'lishi shart, firewall da shu portlar ochiladi. Kalit `LIVEKIT_API_KEY/SECRET` (`make init` sirni yaratadi); bo'sh bo'lsa qo'ng'iroqlar o'chirilgan va `/calls` ogohlantiradi.
- **Qo'ng'iroq** (`/calls/new`): xodim istalgan faol foydalanuvchiga audio/video qo'ng'iroq qiladi. Qabul qiluvchida har sahifada panel chiqadi ("Javob berish" / "Rad etish", 45 soniya); javob bo'lmasa **o'tkazib yuborilgan** (xabar bilan), chaqiruvchi o'zi chiqsa bekor. **Konferensiya**: nom, rejalangan vaqt (qatnashchilar 15 daq oldin qo'shila oladi), qatnashchilar ro'yxati; boshlanmaguncha `/calls/:id/edit` da tahrirlanadi.
- **Xona** (`/calls/:id`): kamera/mikrofon/ekran ulashish, kim gapirayotgani, "Chiqish" va mezbon (yoki `calls.manage`) uchun "Hamma uchun tugatish" (LiveKit xonasi ham yopiladi). Token faqat taklif qilinganlarga beriladi (2 soat, server tomonida imzolanadi).
- **Tarix:** har qatnashchining qo'shilgan vaqti va davomiyligi, tugash sababi (mezbon / administrator / hamma chiqdi / eskirgan). Faqat o'z qo'ng'iroqlarini ko'radi; `calls.read` (direktor) va `calls.manage` (HR) hammasini ko'radi.
- **Ishonchlilik:** LiveKit webhook (`/api/v1/calls/webhook`, JWT imzo + tana hash i tekshiriladi) brauzer yopilgani kabi hollarda holatni to'g'rilaydi; worker `calls_watch` (har 20 s) javobsizlarni yopadi, bo'sh konferensiyani 15 daqiqadan keyin tugatadi.
- Ruxsatlar: `calls.own` (hamma rol), `calls.read`, `calls.manage`.
- **Cheklov:** media (kamera/mikrofon, NAT ortida) lokal brauzer panelida sinab bo'lmaydi; real telefon va turli tarmoqda sinash kerak (HTTPS shart, 7881/7882 ochiq bo'lishi kerak).

## Resepshin va AyTi (F24)

- **Mehmon qaydi** (`/reception`, modul `reception`): xodim mehmonni **oldindan yozadi** (`/reception/new`, kutilayotgan vaqt shart; qabul qiluvchi xodimga xabar boradi). Resepshin (`reception.desk`) mehmon kelganda **"Keldi"** (yorliq/beyj raqami bilan) va ketganda **"Ketdi"** ni belgilaydi; kutmasdan kelganini bir qadamda "yozish va keldi" qilish mumkin. Mehmon kelganda qabul qiluvchiga xabar boradi. Holatlar: kutilmoqda → ichkarida → ketdi; bekor qilindi; kutilgan vaqtdan 4 soat o'tib kelmasa **kelmadi** (worker, har 15 daq).
- Ko'rish: oddiy xodim faqat o'zi yozganlarni ko'radi; resepshin va direktor/HR hammasini (`reception.read`). Hisobot (`/reception/report`): jami tashrif, hozir ichkarida, kelmaganlar, o'rtacha turish vaqti, kunlar/maqsad bo'yicha, eng ko'p mehmon qabul qilganlar. Barcha amallar auditga yoziladi.
- **AyTi ticket** (`/helpdesk`, modul `it_desk`): xodim ticket yuboradi (kategoriya, ustuvorlik, qurilma, skrinshot). Kategoriyada standart ijrochi bo'lsa avtomatik tayinlanadi, bo'lmasa AyTi xodimlariga "Navbat" da chiqadi va xabar boradi. Oqim: **yangi → jarayonda ⇄ javob kutilmoqda → hal qilindi → yopildi**; so'rovchi hal qilinganini tasdiqlab baholaydi (1–5) yoki **qayta ochadi**; hal qilingan ticket 72 soat tasdiqlanmasa avtomatik yopiladi.
- **SLA:** ustuvorlikka qarab javob muddati (shoshilinch 4, yuqori 8, oddiy 24, past 72 soat). Muddat o'tsa (worker) ticket "SLA o'tgan" deb belgilanadi, ijrochi va menejerlarga xabar yuboriladi va audit yoziladi. **Ichki izoh** faqat AyTi xodimlariga ko'rinadi.
- Tahlil (`/helpdesk/analytics`): ochilgan/hal qilingan, SLA ga ulgurish, qayta ochilish ulushi, o'rtacha birinchi javob (daq) va hal qilish vaqti, baho, kategoriya va ijrochi bo'yicha. Kategoriyalar `/helpdesk/categories` (menejer). Hamma create/update alohida sahifada.
- Ruxsatlar: `reception.own` / `helpdesk.own` (hamma rol), `reception.desk` (resepshin, HR), `reception.read` (direktor), `helpdesk.work` (AyTi), `helpdesk.read`, `helpdesk.manage` (HR).

## Ko'chma davomat va jonli kuzatuv (F23)

- **Ikki kalitli ruxsat:** HR xodimga ruxsat beradi (`/mobile/permits`: ish vaqti oynasi, yuborish oralig'i 15–600 s), xodimning o'zi esa `/mobile/my` sahifasida **rozilik** beradi. Ikkalasi bo'lmasa kuzatuv ishlamaydi. Rozilikni xodim istalgan paytda qaytarib olishi mumkin: faol sessiya darhol tugaydi.
- **Ish kuni sessiyasi:** xodim "Ish kunini boshlash" ni bosganda sessiya ochiladi va davomatga `mobile` usulida "keldi" yoziladi (ochiq yozuv bor yoki bugun yopilgan bo'lsa, yangisi yaratilmaydi); "Tugatish" da "ketdi" yoziladi. **Trek faqat sessiya davomida va ruxsat etilgan oynada** yoziladi; oyna tugagach (+30 daq) sessiya avtomatik yopiladi, davomatga ketish oyna oxirida yoziladi.
- **Trek:** telefon har interval soniyada batch yuboradi (tarmoq yo'q bo'lsa 2000 nuqtagacha xotirada saqlanadi); aniqlik > 100 m, takror, kelajak va imkonsiz tezlikdagi (> 250 km/soat) nuqtalar tashlanadi; masofa metr aniqligida yig'iladi.
- **Batareya va ruxsat holati:** har batch bilan batareya darajasi, zaryadlanishi, geolokatsiya ruxsati va GPS holati yuboriladi. Xavfsizlik hodisalari (menejerlarga xabar bilan, `/mobile/events`): **SOS** (xodim tugmasi, sessiyasiz ham ishlaydi), batareya ≤ 15% (bir marta, 30% dan keyin qayta), geolokatsiya ruxsati yo'qoldi, GPS o'chirildi, **signal uzildi** (10 daq nuqta yo'q; tiklanganda "signal tiklandi"), sessiya avtomatik yopildi. Menejer hodisani izoh bilan "ko'rib chiqildi" qiladi.
- **Jonli xarita** (`/mobile`, 10 soniyada yangilanadi): ish kunidagilar, batareya, signalsizlar, ochiq hodisali xodimlar qizil. Sessiyalar tarixi va trek xaritasi (`/mobile/sessions`).
- **Maxfiylik:** trekni ko'rish auditga yoziladi (`mobile.view_track`); nuqtalar 90 kundan keyin o'chiriladi; rozilik, boshlash, tugatish, SOS, ruxsat o'zgarishi ham auditda.
- Ruxsatlar: `mobile.own` (hamma rol: rozilik, ish kuni, SOS), `mobile.read` (direktor), `mobile.manage` (HR).
- **Cheklov:** brauzer (PWA) fonda GPS ni kafolatlamaydi: ekran o'chganda yoki ilova yopilganda iOS/Android nuqtalarni to'xtatishi mumkin (Wake Lock ekranni yoqib turadi). Haqiqiy fon rejimi uchun mahalliy ilova kerak bo'ladi; signal uzilishi hodisasi aynan shu holatni ko'rsatadi.

## Omborxona (F22)

- **Erkin grafik:** ombor yaratilganda (`/warehouse/new`) smena oynasi (standart **08:00 → 07:00**, keyingi kunga o'tadi) va minimum soat (standart 9) kiritiladi; "erkin" smena turi va `warehouse` toifali ish guruhi avtomatik yaratiladi (yoki mavjud guruh tanlanadi). Xodim oyna ichida istalgan vaqtda keladi/ketadi, kechikish hisoblanmaydi; minimumdan kam ishlagan kun tabelda "kam ishladi" bo'ladi.
- **Xodimlar tarkibi** (`/warehouse/:id`): xodimning ish guruhi ombor guruhiga o'tkaziladi (boshqa omborda bo'lsa ko'chiriladi), chiqarilsa standart guruhga qaytadi. Smena grafigi va davomat (F5–F8) o'zgarishsiz ishlaydi.
- **Holat** (`/warehouse`, 30 soniyada yangilanadi): joriy smena oynasi, kim ishda, necha soat ishlagan, minimumga yana qancha qolgan, tugatganlar va minimumdan kam ishlaganlar, kelmaganlar. Ishdagilar soni `kamida ishda` dan kam bo'lsa — "xodim yetishmayapti".
- **Nazorat** (`/warehouse/:id/control`, 42 kungacha): xodimlar bo'yicha soat, o'rtacha va eng uzun smena, minimumdan kam kunlar, kelmagan, ketishi belgilanmagan; kunlar bo'yicha eng ko'p/eng kam bir vaqtdagi xodim va yetishmovchilik daqiqalari (smena oynasi bo'yicha oraliqlar hisoblanadi).
- **Ogohlantirish:** worker har 10 daqiqada tekshiradi: yetishmovchilik `grace` (standart 20 daq) dan oshsa va juda uzoq ochiq smena (standart > 16 soat) uchun menejerlarga bir martadan xabar; yetishmovchilik tugasa holat tozalanadi.
- Ruxsatlar: `warehouse.read` (direktor, logistika), `warehouse.manage` (HR). Audit: `warehouse.*`. Ombor o'chirilsa, guruh va smena saqlanadi.

## Logistika (F21)

- **Mashinalar** (`/logistics/vehicles`): davlat raqami (katta harfga keltiriladi, takrorlanmaydi), tur, yoqilg'i turi va **me'yor (l/100 km)**, odometr, filial, holat. Reysi bor mashina o'chirilmaydi.
- **Hujjatlar** (mashina kartasida): texpasport, sug'urta, OSAGO, texnik ko'rik, ruxsatnoma va muddatlari. Worker har kuni (08:10) tekshiradi: muddatga 30 va 7 kun qolganda hamda o'tganda logistika menejerlariga **bir martadan** xabar beradi (muddat o'zgarsa, eslatmalar qaytadan). Haydovchilik guvohnomasi ham shunday.
- **Haydovchilar** (`/logistics/drivers`): xodim + guvohnoma ma'lumoti. Reys faqat haydovchi sifatida kiritilgan xodimga biriktiriladi; GPS yuborish uchun xodimda tizim hisobi (`haydovchi` roli) bo'lishi kerak.
- **Reyslar** (`/logistics/trips`): rejalashtirilgan → yo'lda → yakunlangan/bekor. Boshlashda odometr (mashinadagidan kam bo'lmasin), yakunlashda odometr: masofa = farq, me'yor bo'yicha yoqilg'i = masofa × me'yor / 100 (yakunlanganda muhrlanadi). Bir mashina/haydovchida bitta faol reys.
- **Jonli GPS** (`/logistics`): haydovchi telefonida `/logistics/my` sahifasi (PWA) faol reys davomida joylashuvni kuzatadi va har 15 soniyada yuboradi (tarmoq bo'lmasa, 2000 nuqtagacha xotirada saqlab, keyin yuboradi; ekran o'chmasligi uchun Wake Lock). Server aniqligi 100 m dan yomon, takror, kelajakdagi nuqtalarni tashlaydi. **Reysdan tashqarida kuzatuv yo'q** (faol reys bo'lmasa, nuqta qabul qilinmaydi). Xarita har 10 soniyada yangilanadi; 5 daqiqa signalsiz mashina "signal yo'q" deb belgilanadi. Reys tugagach trek xaritada chiziq bo'lib ko'rinadi, GPS masofasi hisoblanadi (imkonsiz "sakrash"lar kesiladi).
- **Yoqilg'i** (`/logistics/fuel`): quyilgan litr, narx, summa, odometr, shahobcha; haydovchi faqat o'z faol reysi uchun kiritadi, boshqaruvchi istalgan mashinaga.
- **Hisobotlar** (`/logistics/reports`): yoqilg'i (me'yor bo'yicha litr, quyilgan litr, farq, amalda l/100 km, summa; Excel), reyslar (haydovchi bo'yicha), **GPS ish kuni** (haydovchining kun bo'yicha birinchi/oxirgi signali, soat, km), muddatlar.
- Ruxsatlar: `logistics.own` (haydovchi), `logistics.read`, `logistics.manage`. Yangi rollar: `haydovchi`, `logistik`. Audit: `logistics.*`.
- **Eslatma:** "GPS davomat" hozircha GPS ish kuni hisoboti ko'rinishida (davomat yozuvi yaratmaydi). Ko'chma xodimlarning davomati va trek F23 da.

## Abet (F20)

- **Menyu** (`/canteen/menus`): kunlik taomlar (turi bilan), haftalik ko'rinish; yaratish/tahrirlash alohida sahifada. Taomni tahrirlasangiz baholari saqlanadi, olib tashlasangiz ular ham o'chadi. Baholari bor menyu o'chirilmaydi va sanasi o'zgarmaydi.
- **Baholash** (`/canteen`, `/canteen/rate?t=`): xodim kunning umumiy bahosini (1–5), har taomni, izoh va "anonim" belgisini yuboradi; qayta yuborsa yangilanadi, olib tashlash mumkin. Faqat tizim hisobi ulangan faol xodim baholaydi. Menyu kunidan oldin baholab bo'lmaydi; kundan keyin `rating_days` (standart 1) kun ichida mumkin.
- **QR** (`/canteen/qr`): abetga yopishtiriladigan o'zgarmas QR (HMAC); skanerlansa bugungi menyu ochiladi. "QR majburiy" yoqilsa, faqat QR orqali baholash mumkin (`/canteen/settings`). QR almashtirilsa eskisi ishlamaydi.
- **Izohlar** (`/canteen/comments`): baho va sana bo'yicha filtr, javobsizlar; anonim izohda ism faqat `canteen.manage` ga ko'rinadi; boshqaruvchi javob yozadi (xodimga xabar boradi). 2★ va past baho menejerlarga xabar bo'ladi.
- **Tahlil** (`/canteen/analytics`): o'rtacha baho, baholaganlar / faol xodimlar, past baholar ulushi, taqsimot, kunlik dinamika, taomlar reytingi (bir xil nom turli kunlarda birlashadi).
- Ruxsatlar: `canteen.own` (hamma: ko'rish va baholash), `canteen.read` (izoh va tahlil: direktor), `canteen.manage` (menyu, QR, sozlamalar, javob: HR). Audit: `canteen.*`.

## Moliya: oylik (F19)

- **Sxemalar** (`/payroll/schemes`): xodim uchun oklad, savdodan %, reja bonusi va KPI maksimumi; `Amal qila boshlaydi` bilan versiyalanadi (oy oxirigacha kuchga kirgan eng yangi sxema qo'llanadi).
- **Kiritmalar** (`/payroll/items`): oy bo'yicha savdo (fakt), reja, KPI bali (0–100), bonus, avans, ushlanma; CSV matnidan ommaviy kiritish (avval tekshiruv, keyin qo'llash). Oy tasdiqlangach kiritmalar yopiladi.
- **Hisob-kitob** (`/payroll/runs`): oyga bitta; holat qoralama → tasdiqlangan → to'langan. Formulalar:
  - oklad = fix × to'langan kun / reja kun (reja kun = grafik bo'yicha ish kunlari; sababsiz kelmagan kun to'lanmaydi, tasdiqlangan ruxsat sozlamaga qarab to'lanadi; ishga olingan/bo'shatilgan sanadan tashqari kunlar hisobga kirmaydi). Kunlar tabel bilan bir manbadan (`day_status`);
  - komissiya = savdo × %; reja bonusi: savdo ≥ reja bo'lsa; KPI bonusi = KPI maks × ball%; + qo'lda bonuslar = **yalpi**;
  - soliq bazasi = yalpi − tasdiqlangan jarimalar (F11) − ushlanmalar; JShDS 12% va INPS 0,1% (hisob-kitob yaratishda o'zgartiriladi va muhrlanadi); sof = baza − soliq − INPS; **to'lanadi** = sof − avans.
  - Hamma summa so'mgacha yaxlitlanadi (ROUND_HALF_UP). Qo'lda hisob bilan mosligi testlarda tekshirilgan.
- **Tasdiqlash:** hisobdan keyin kiritma, jarima yoki sxema o'zgargan bo'lsa tasdiqlab bo'lmaydi (qayta hisoblash kerak). Tasdiqlangach satrlar muhrlanadi (sxema keyin o'zgarsa ham o'zgarmaydi), xodimlarga varaqa xabari boradi. Qayta ochish (to'lanmagan bo'lsa) va "to'langan" belgisi bor.
- **Ogohlantirishlar:** sxemasiz faol xodimlar, ketish belgilanmagan/kam ishlangan kunlar, tugamagan oy, KPI kiritilmagani, tasdiqlanmagan jarimalar, manfiy to'lov.
- **Eksport:** Excel (`/payroll/runs/:id/export`, jami qatori formula bilan). **Mening varaqam** (`/payroll/my`): xodim faqat tasdiqlangan oylarini va tafsilotini ko'radi.
- Hamma amal auditda (`payroll.*`). Ruxsatlar: `payroll.own` (hamma), `payroll.read` (HR menejer, direktor), `payroll.input` (HR menejer), `payroll.manage` (HR direktor).

## Stajirovka (F18)

- **Dastur** (`/internship/programs`): tartiblangan bosqichlar, standart o'tish bali, "ketma-ket ochiladi" rejimi. Bosqich turlari: **video** (YouTube/Vimeo ichida ko'rsatiladi, boshqa havola yangi oynada), **hujjat** (fayl yoki havola), **matn**, **test**.
  Bosqichlarni yuqoriga/pastga surish mumkin; har bosqich majburiy yoki ixtiyoriy. Stajyori bor dastur o'chirilmaydi, nofaol qilinadi.
- **Test:** bitta yoki bir nechta to'g'ri javobli savollar (bir nechta bo'lsa hammasini tanlash kerak, qisman to'g'ri = noto'g'ri), o'tish bali va urinishlar soni (0 = cheksiz). Stajyor API da to'g'ri javoblarni ko'rmaydi; muvaffaqiyatsiz urinishda faqat xato savollar belgilanadi.
  Urinishlar tugasa, murabbiy yoki HR bosqichni qayta ochadi.
- **Biriktirish** (`/internship/enrollments/new`): xodim + dastur + murabbiy + muddat. Stajyor faqat o'z faol stajirovkasini o'qiydi (xodim kartasi tizim hisobiga ulangan bo'lishi kerak); ketma-ket rejimda qulflangan bosqichga o'tib bo'lmaydi.
- **«Ishga tayyor»:** hamma majburiy bosqich bajarilganda holat avtomatik "tayyor" bo'ladi (o'rtacha test bali saqlanadi), murabbiy va HR ga xabar boradi. Murabbiy yoki HR tasdiqlasa, stajirovka "yakunlangan"; stajyorga xabar boradi. Stajyor o'zini tasdiqlay olmaydi.
- **Progress:** foiz, o'rtacha ball, muddatdan o'tganlar (`/internship`). Audit: biriktirish, bosqich, test, qayta ochish, tasdiqlash, bekor qilish (`internship.*`).
- Ruxsatlar: `internship.own` (stajyor va murabbiylar: mudir, koordinator), `internship.read`, `internship.manage`.

## Nomzodlar va ish o'rinlari (F17)

- **Vakansiya** (`/recruit/vacancies`): nom, filial/bo'lim/lavozim, o'rinlar soni, maosh oralig'i, rekruter, muddat, tavsif va talablar. Holat: qoralama → ochiq ↔ to'xtatilgan → yopilgan. Arizasi bor vakansiya o'chirilmaydi, yopiladi.
  Vakansiya sahifasida pipeline ustunlari (yangi, saralash, suhbat, taklif, ishga olingan, rad etilgan) ko'rinadi.
- **Nomzodlar** (`/recruit/candidates`): ism, telefon (+998, takrorlanmaydi), email, sana, manba, ko'nikmalar, rezyume fayllari. **Matndan to'ldirish**: rezyume matnini joylab, ism/telefon/email/sana/manzil/ko'nikmalar ajratib olinadi.
  Hozir qoidalar asosida (`engine: rules`); LLM provayderi AI fazasida ulanadi, forma va endpoint (`POST /recruit/candidates/parse`) o'zgarmaydi.
- **Arizalar** (`/recruit/applications`): nomzod va vakansiya juftligi (takrorlanmaydi), rekruter, baho (1–5), suhbat vaqti, izohlar, rad etish sababi (qayta ochish mumkin). Har o'tish, rad etish va izoh tarixda va auditda.
- **Xodimga aylantirish** (`/recruit/applications/:id/hire`, faqat «taklif» bosqichidan, `employees.create` kerak): ism familiya/ism/otasining ismiga bo'linadi, vakansiyadagi bo'lim/lavozim/filial taklif qilinadi, o'xshash xodim (telefon, ism+sana) bo'lsa tasdiq so'raladi.
  Xodim kartasi va «ishga olindi» tarixi yaratiladi, o'rinlar to'lsa vakansiya avtomatik yopiladi, rekruterga xabar boradi.
- **Tahlil** (`/recruit/summary`): arizalar, ishga olingan, rad etilgan, o'rtacha ishga olish kunlari, voronka va manbalar kesimi.
- Ruxsatlar: `recruit.read` (direktor ham ko'radi), `recruit.manage` (HR). Ommaviy ariza topshirish sahifasi (tashqaridan) hozircha yo'q: arizalarni rekruter kiritadi.

## Koordinator checklist (F16)

- **Filialga borish** (`/checklists/new`): koordinator o'z filialini va shablonni tanlaydi, brauzer joylashuvini tasdiqlaydi. Filial geofensidan (standart 100 m) tashqarida bo'lsa, sabab yozilmaguncha boshlab bo'lmaydi;
  sabab bilan boshlangan tekshiruv "filialdan tashqarida" deb belgilanadi va masofa saqlanadi. Filial koordinatasi yo'q bo'lsa GPS tekshirilmaydi. Bir filialga bitta qoralama.
- **To'ldirish** (`/checklists/:id/fill`): Ha/Yo'q yoki 1–5 baho, izoh, har bandga rasm, "kerak emas" (faqat majburiy bo'lmagan bandda). Qoralama saqlanadi; majburiy bandlar to'lmaguncha yuborib bo'lmaydi. Yuborilgan tekshiruv o'zgarmaydi.
- **Ball**: vazn bo'yicha (yes/no: 0 yoki 1, baho: qiymat/5); "kerak emas" bandlar hisobga kirmaydi. Kritik band bajarilmasa (yo'q yoki baho ≤1) hisoblanadi va HR ga xabar boradi, 60% dan past ball ham.
  Mudir o'z filialining yuborilgan tekshiruvini ko'radi va xabar oladi.
- **Shablonlar** (`/checklists/templates`, `checklists.manage`): bandlar, bo'lim, vazn, majburiy/kritik; tahrirlash eski tekshiruvlarga ta'sir qilmaydi (har tekshiruv o'z nusxasini saqlaydi). Tekshiruvli shablon o'chirilmaydi, nofaol qilinadi.
- **Qamrov, reyting, trend** (`/checklists/report`): har filial uchun davrdagi borishlar, o'rtacha ball, oxirgi borish va "N kundan ortiq tekshirilmagan" belgisi (7/14/21/30 kun), filiallar va koordinatorlar reytingi, haftalik o'rtacha ball chizig'i.
- **Audit**: boshlash, yuborish, o'chirish va shablon o'zgarishlari (`checklists.*`). Ruxsatlar: `checklists.own` (koordinator, mudir), `checklists.read`, `checklists.manage`.

## Ehtiyojlar (F15)

- **4 bosqichli oqim** (`/needs`, `/needs/:id`): so'rash → ijrochi tayinlash → bajarish (hisobot + fayllar) → tasdiq (1–5 baho). Holatlar: so'ralgan, bajarilmoqda, tasdiq kutilmoqda, tasdiqlangan, bekor qilingan.
  Tasdiqlovchi "yetarli emas" desa, ish sababi bilan ijrochiga qaytadi (qaytishlar soni saqlanadi); so'rov tasdiqdan oldin bekor qilinishi mumkin. Bosqich amallari tafsilot sahifasining o'zida (alohida modal yo'q).
- **Kategoriyalar** (`/needs/categories`, `needs.manage`): standart ijrochi va muddat (kun). Kategoriyali so'rov avtomatik ijrochiga tushadi va muddati hisoblanadi; ijrochisiz so'rov dispetcherlarga (`needs.dispatch`) xabar bo'ladi.
  Boshlang'ich 4 kategoriya migratsiya bilan keladi. So'rovi bor kategoriya o'chirilmaydi, faqat nofaol qilinadi.
- **Muddat**: worker har 15 daqiqada tekshiradi: 24 soat qolganda "yaqin", o'tganda "o'tdi" xabari (har biri bir martadan); "o'tdi" auditga ham yoziladi.
- **Audit**: har bosqich (`needs.request/assign/complete/confirm/return/cancel/update/overdue`) auditga yoziladi va so'rov tarixida (`need_events`) ko'rinadi.
- **Tahlil** (`/needs/analytics`): yaratilgan/bajarilgan, muddatda bajarilish, qaytarilganlar ulushi, o'rtacha vaqt va baho; kategoriya, ijrochi va filial kesimi.
- Ruxsatlar: `needs.own` (hamma rollar: so'rash va o'z so'rovlari), `needs.work` (ijrochi: IT, omborxona, HR), `needs.dispatch` (hammasini ko'rish, tayinlash), `needs.manage`.

## Topshiriqlar (F12)

- **Ko'rinishlar**: kanban doska (`/tasks/board`, kartani sudrab ustunlar orasida yoki ustun ichida ko'chirish; tartib saqlanadi, telefonda/klaviaturada karta ichidagi tanlov),
  ro'yxat (`/tasks`, filtr va saralash), kalendar (`/tasks/calendar`, muddat bo'yicha). Ustunlar: bajarilishi kerak, jarayonda, tekshiruvda, bajarildi (doskada oxirgi 14 kun).
- **Holat qoidalari**: ijrochi "tekshiruvda"gacha olib boradi, "bajarildi"ga faqat yaratuvchi (yoki `tasks.manage`) o'tkazadi; o'ziga o'zi bergan topshiriqni o'zi yopadi;
  qayta ochish yaratuvchida. Boshqalarga topshiriq berish `tasks.assign` ruxsatini talab qiladi (xodim faqat o'ziga).
- **Chat**: topshiriq ichidagi izohlar (har 8 soniyada yangilanadi), ishtirokchilarga bildirishnoma; **fayllar** (PDF/rasm/Office, 15 MB, 20 tagacha, faqat API orqali);
  **tarix** (yaratildi, holat, o'zgarishlar, fayl, izoh, muddat o'tdi); kuzatuvchilar, teglar, ustuvorlik (past...shoshilinch).
- **Shablonlar** (`/tasks/templates`): sarlavha, tavsif, ustuvorlik, muddat (kun), teglar; yangi topshiriq formasida tanlansa to'ldiriladi.
- **Muddat nazorati**: worker har 15 daqiqada: 24 soat qolganda ijrochiga, muddat o'tganda ijrochi va yaratuvchiga bir martadan xabar (muddat o'zgarsa qayta).
- **Tahlil** (`/tasks/analytics`): yaratilgan/bajarilgan, ochiq, muddati o'tgan, o'z vaqtida bajarish ulushi, o'rtacha bajarish vaqti, kunlik dinamika, holat/ustuvorlik taqsimoti, ijrochilar kesimi (o'zimniki yoki hammasi).
- Ko'rinish: ishtirokchi (yaratuvchi/ijrochi/kuzatuvchi) o'z topshirig'ini, `tasks.read`/`tasks.manage` hammasini ko'radi. Topshiriq o'chirilmaydi, arxivlanadi.
- Ruxsatlar: `tasks.own`, `tasks.assign`, `tasks.read`, `tasks.manage` (istalganini tahrirlash, shablonlar).

## Jarimalar (F11)

- **6 bosqichli qoidalar** (`/penalties/rules`): har bosqichda nom, summa (so'm) va blok kunlari. Summa 0 = ogohlantirish; blok > 0 = hisob vaqtincha o'chadi.
  Bosqich xodimning oyna (standart 90 kun) ichidagi oldingi jarimalari soniga bog'liq: 0 ta -> 1-bosqich ... 5+ -> 6-bosqich; hamma tur birgalikda yoki har tur alohida sanaladi.
  Boshlang'ich summalar MISOL: mijoz o'z siyosatiga moslaydi.
- **Versiyalash**: qoidani o'zgartirish yangi versiya yaratadi (kim, qachon, izoh); har jarima o'z versiyasiga bog'langan va bosqich/summa/blok/nom hisoblangan paytda
  muhrlanadi, shuning uchun qoida o'zgarsa tarix buzilmaydi.
- **Avtomatik hisob**: davomat kun holatidan (`day_status`, tabel bilan bir manba) kechikish (chegara daqiqa), erta ketish, kelmaslik, ketish belgilanmaganligi aniqlanadi.
  `/penalties/scan` da avval ko'rib chiqish, keyin yozish; qayta ishga tushsa takrorlanmaydi; faqat tugagan kunlar. Tasdiqlangan ruxsat va "davomat shart emas" guruhlari jarimalanmaydi.
  Qoidada "avtomatik hisob" yoqilsa worker har kecha (02:30) oxirgi 3 kunni hisoblaydi (standart: o'chiq).
- **Tasdiq**: hisoblangan jarimalar `pending` bo'ladi va HECH KIMGA o'zi qo'llanmaydi. Tasdiqlovchi (`penalties.approve`) tasdiqlaydi yoki izoh bilan bekor qiladi;
  o'z jarimasini tasdiqlay olmaydi. Xodimga bildirishnoma (app + Telegram), hammasi auditda. Qo'lda jarima (`/penalties/new`) ham tasdiq kutadi.
- **Blok**: blokli bosqich tasdiqlansa xodimning kirish hisobi o'chiriladi va sessiyalari yopiladi; muddat tugagach worker (har soat) qayta yoqadi; bekor qilinsa darhol yoqiladi.
  Bo'shatilgan xodim hisobi hech qachon qayta yoqilmaydi.
- **Hisobot** (`/penalties/report`): xodim/bo'lim/filial/tur kesimida tasdiqlangan va kutilayotgan summalar, Excel eksport (oylik hisobi F19 shu ma'lumotdan foydalanadi).
- Ruxsatlar: `penalties.own`, `penalties.read`, `penalties.approve`, `penalties.manage` (qoidalar, avtomatik hisob, qo'lda jarima).

## Tushuntirish xatlari (F10)

- **Oqim**: HR/koordinator xodimdan tushuntirish so'raydi (`/letters/new`, kunlik davomatdagi kech/kelmagan/erta ketgan qatorlardan bir bosishda to'ldirilgan holda) ->
  xodim matn yozib, parolini kiritib elektron imzolaydi (`/letters/:id/write`) -> HR qabul qiladi yoki izoh bilan qaytaradi (qayta yozadi). Muddat o'tsa belgilanadi.
  Koordinator faqat o'z filiali xodimidan so'ray oladi; hammasi tarixda va auditda; bildirishnomalar app ichida va Telegramda.
- **Shablon** (`/letters/templates`): hujjat sarlavhasi, qabul qiluvchi, matn (`{employee_name} {position} {department} {incident_date} {incident} {explanation} ...`),
  xodimga ko'rsatma. Noma'lum belgi rad etiladi. Imzolash paytida matn va shablon xat ichiga MUHRLANADI: keyin shablon o'zgarsa ham eski xat buzilmaydi.
- **Imzo va yaxlitlik**: imzo paytida SHA-256 hisoblanadi (matn, raqam, imzolovchi, vaqt). Parol 5 marta xato kiritilsa 10 daqiqaga bloklanadi.
  Bu oddiy elektron imzo (parol bilan tasdiqlash), malakali ERI emas: qonuniy kuchi mijoz yurisdiksiyasiga bog'liq, yurist bilan tekshiring.
- **PDF**: server tomonida (reportlab), imzo bloki va tekshirish QR kodi bilan. Gotenberg qo'shilmadi: qo'shimcha servis kerak bo'lmadi.
- **QR tekshiruv** (ochiq, kirishsiz): `/verify/:code`. Faqat raqam, qisqartirilgan ism, holat, imzo vaqti va yaxlitlik ko'rsatiladi (matn yo'q); qog'oz nusxadagi
  SHA-256 ni solishtirish mumkin; bazadagi matn o'zgartirilsa "o'zgartirilgan" deb chiqadi. IP bo'yicha daqiqasiga 60 so'rov. `/verify` da kamera bilan QR skanerlash
  (brauzer BarcodeDetector ni qo'llasa) yoki kodni qo'lda kiritish.
- **Skaner**: qog'ozga chop etib qo'lda imzolangan nusxani PDF/JPG/PNG sifatida yuklash (`/letters/:id/scan`, telefonda kamera bilan); faqat API orqali, ruxsat tekshiruvi bilan beriladi.
- Ruxsatlar: `letters.own`, `letters.issue`, `letters.read`, `letters.review`, `letters.manage`.

## Javob olish (F9)

- **So'rov**: xodim kunlik (bir necha kun, <= 31) yoki soatlik (15 daq - 12 soat) ruxsat so'raydi: `/answers/new`. Sabab turi (kasallik, oilaviy, shaxsiy, xizmat, boshqa).
  7 kungacha orqaga sanaga mumkin; faol so'rovlar bilan kesishish rad etiladi.
- **Yo'naltirish**: xodim filialining koordinatoriga; koordinator yo'q bo'lsa to'g'ridan-to'g'ri HR ga. Koordinator `ANSWERS_ESCALATION_HOURS` (8) soat ichida
  javob bermasa, worker (har 5 daqiqada) so'rovni HR ga o'tkazadi; HR va xodimga bildirishnoma ketadi. Kechikib kelgan koordinator endi qaror chiqara olmaydi.
- **Qaror**: tasdiqlash yoki rad etish (rad uchun izoh majburiy), xodim o'z so'roviga qaror chiqara olmaydi. Boshlanmagan so'rovni xodim bekor qila oladi.
- **Tarix**: har qadam (yuborildi, eskalatsiya, qaror, bekor) timeline sifatida; hammasi auditda. Bildirishnomalar app ichida va Telegramda.
- **Davomat bilan bog'liq**: tasdiqlangan KUNLIK ruxsat tabel/dashboardda "Ruxsat bilan" (R) bo'ladi va kelmagan hisoblanmaydi. Soatlik ruxsat hozircha
  kechikish/erta ketishni avtomatik oqlamaydi (kalendar va tarixda ko'rinadi).
- **Ko'rinish**: xodim o'zinikini; koordinator o'z filiallaridagi so'rovlarni; `answers.read` hammasini; `answers.manage` (HR) istalganiga qaror chiqaradi.
  `/answers/inbox` (menyuda kutayotganlar soni), `/answers/calendar` (oy kalendari).
- Ruxsatlar: `answers.request`, `answers.read`, `answers.decide`, `answers.manage`.

## Davomat tahlili (F8)

- `/attendance/dashboard`: davr (bugun, hafta, oy, o'tgan oy, oraliq; <= 62 kun) va filtrlar (xodim, bo'lim, filial, guruh) bo'yicha ko'rsatkichlar:
  davomat foizi, kelgan/kelmagan kunlar, kechikishlar, o'z vaqtida kelish, ishlagan soat; kunlik dinamika; bo'lim va filial kesimi (eng past foiz tepada);
  eng ko'p kechikkan/kelmaganlar; kunlar holati taqsimoti.
- **Bitta manba**: dashboard ham, tabel ham, kunlik hisobot ham bir funksiyadan (`day_status`) hisoblanadi, test jami raqamlar tabel bilan tengligini tekshiradi.
  Foiz = kelgan / (kelgan + kelmagan): kutilayotgan, kelgusi, dam va bayram kunlari kirmaydi.
- **PDF eksport** (uz/ru): server tomonida (reportlab, DejaVu shrifti imidj yig'ishda yuklanadi); eksport auditga yoziladi.
- Ruxsat: `attendance.read`.

## Face ID (F7)

- **Dvigatel**: serverda OpenCV (YuNet aniqlash + SFace tanish, ONNX, Apache-2.0). Modellar Docker imidjini yig'ishda SHA-256 bilan tekshirib yuklanadi (`/opt/models`).
  Rasm hech qachon saqlanmaydi, faqat 128 sonli shablon.
- **Rozilik** (`/face/consent`): xodimning O'ZI beradi, matn versiyalangan (`FACE_CONSENT_VERSION`). Qaytarib olinsa shablonlar darhol o'chadi.
  Rozilik matni yuridik ko'rikdan o'tishi kerak (mijoz mamlakati qonunlariga moslash).
- **Ro'yxatga olish** (`/face/enroll`) va **belgilash** (`/face/punch`): kamera oldida tasodifiy ketma-ketlikdagi harakat (to'g'ri qarash, chapga, o'ngga burilish).
  Server har kadrda burilishni landmarklardan hisoblaydi, ketma-ketlik va bitta shaxs ekanini tekshiradi; challenge bir martalik.
  Bu faol liveness, lekin sertifikatlangan PAD (video/niqob hujumlariga qarshi) EMAS: yuqori xavfli joylarda QR/GPS bilan birga ishlating.
- **Shifrlash**: shablon AES-256-GCM bilan, kalit `FACE_ENCRYPTION_KEY` (yo'q bo'lsa SECRET_KEY) dan; xodim ID si AAD, shablonni boshqa xodimga ko'chirib bo'lmaydi.
- **Dublikat**: boshqa xodimning yuzi bilan ro'yxatdan o'tib bo'lmaydi (do'stining nomidan belgilashga qarshi); urinish auditga yoziladi.
- **Bloklash**: 8 xato urinishdan keyin 10 daqiqaga Face ID bloklanadi (QR/GPS ishlayveradi).
- **Saqlash muddati**: shablon `FACE_RETENTION_DAYS` (365) kun tekshirilmasa, bo'shatilgach `FACE_DISMISSED_RETENTION_DAYS` (30) kundan keyin, rozilik qaytarilganda avtomatik o'chadi (worker, har kuni 03:45).
- **HR ko'rishi**: `/face/admin` faqat holatni ko'rsatadi (shablon/rasm yo'q); xodim kartasini ochish auditga yoziladi; o'chirish sabab bilan.
- **Sifat o'lchovi** (`/face/evaluation`): FAR (ro'yxatdan o'tganlar shablonlari o'zaro) va FRR (haqiqiy urinishlar ballari) chegara bo'yicha; chegara `FACE_MATCH_THRESHOLD`.
  Standart 0,40 taxminiy: mijozning haqiqiy xodimlarida o'lchab tanlang.
- Hozircha 1:1 (xodim o'z hisobi bilan kiradi). Filialdagi umumiy terminal (1:N) keyingi fazalarda.
- Ruxsatlar: `face.enroll` (xodimlar), `face.read`, `face.manage`, `face.evaluate`.

## Mijoz (client) extension tizimi

Core hamma uchun bitta. Mijozga xos kod `clients/<nom>/` da, `.env` dagi `CLIENT_NAME` tanlaydi.

| Fayl | Vazifa |
|---|---|
| `client.yaml` | brend (nom, ranglar), modullarni yoqish/o'chirish, mijoz sozlamalari |
| `backend_ext/__init__.py` | `setup(ctx)`: router qo'shish, `ctx.events.on(...)`; `setup_worker(registry)`: fon vazifalari |
| `frontend_ext/index.tsx` | `register(api)`: `addRoute`, `addNavItem`, `slot('nom', Komponent)` |
| `migrations/` | faqat mijoz jadvallari, alohida `alembic_version_ext` jadvali (core bilan to'qnashmaydi) |

Yangi mijoz: `deploy/scripts/new-client.sh acme "Acme HR"`.

Qoida: mijoz kodi core jadvallarini o'zgartirmaydi; core o'zgarsa mijozlar tag bo'yicha yangilanadi.

## Deploy (DigitalOcean)

1. `sudo deploy/scripts/droplet-setup.sh` (firewall, nginx, certbot, docker)
2. Repo ni klonlang, `make init`, `.env` da `CLIENT_NAME` ni belgilang
3. `deploy/host-nginx.conf.example` ni domeningizga moslab qo'ying, `certbot --nginx -d client1.vaksinahr.uz`
4. `make up`: ilova `127.0.0.1:6788` da, host nginx 443 orqali tashqariga beradi
