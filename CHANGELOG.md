# O'zgarishlar tarixi

Format: [Keep a Changelog](https://keepachangelog.com), versiyalash: SemVer (major — buzuvchi o'zgarish).

## [Chiqmagan]

- F47: HR PROFI brendi — logotip (och fon uchun navy, to'q mavzu uchun oq `logo-dark.png`), belgi, favicon, PWA ikonlari, og-image, `theme-color`. Yangi `BrandLogo` komponenti (mijoz logosi bo'lsa avvalgi oq «plashka» saqlanadi).
- `make demo-seed CONFIRM=yes`: barcha bo'limlar uchun namunaviy ma'lumot (avval ish ma'lumotini o'chiradi).

## [1.1.0] — HR jarayonlari, KOSHI tariflari, integratsiyalar (F32–F40)

Migratsiyalar: `0029`–`0036` (api ishga tushganda o'zi qo'llanadi). Batafsil: [docs/F32-F40-XULOSA.md](docs/F32-F40-XULOSA.md).

### Qo'shildi
- **F32 Davomat ishonchliligi:** "Davomat muammosi" so'rovi (xodim → koordinator → HR → davomat avtomatik tuzatiladi), ketishni tasdiqlash dialogi, Face ID yordami.
- **F33 Koordinator hisoboti:** koordinator × smena kesimida kelmagan/kechikkanlar, oy tarixi, uzoq kelmaganlar, sabab va chora izohi (24 soat), har kuni 20:00 avtomatik yuborish.
- **F34 Zayafka → e'lon → manba:** zayafka tasdig'i (zaveduyushiy → HR menejer → HRD), vakansiya avtomatik ochiladi, lavozim talablari va e'lon matni, kanallar, shaxsiy havolalar, ommaviy ariza sahifasi (`/apply/:kod`), manba hisoboti.
- **F35 Nomzod kirishi:** Telegram bot orqali ariza, suhbat natijasi va tajriba darajasi, fon tekshiruv, AI skaner, job offer (HRD tasdig'i), rekruter paneli.
- **F36 Preboarding/onboarding:** filial paketi, 7 kunlik hisobot va fidbek, 7-kun qarori (onboarding avtomatik), oflayn darslar va qatnashuv, kadrovik sahifasi.
- **F37 Attestatsiya va o'sish:** oylik attestatsiya (oy oxirida avtomatik), yig'ma baho, lavozim zinapoyasi, o'sish takliflari (HRD).
- **F38 Ushlab qolish va nazorat:** ketish xavfi holatlari, haftalik uchrashuv, offboarding (exit-intervyu, choralar → vazifalar, dostupni yopish), nazorat paneli, "HR auditor" roli, haftalik avtomatik xavf skaneri.
- **F39 KOSHI tariflari:** START/PRO/PREMIUM (`client.yaml → plan`), foydalanuvchi o'rinlari va litsenziya muddati (`license`), "Tarif va litsenziya" sahifasi, `clients/koshi/` namunasi, [docs/PLANS.md](docs/PLANS.md).
- **F40 Integratsiyalar:** API kalitlari va tashqi API (`/api/ext/v1`: savdo/reja, filiallar, xodimlar), savdo hisoboti, filial reyestrini solishtirish, shikoyat moduli.
- Yangi ruxsatlar: `attestation.*`, `performance.*`, `career.*`, `retention.*`, `control.read`, `integrations.*`, `complaints.*`, `pharmacy.approve`, `recruit.approve`. Mavjud rollarga standart ruxsatlar bir marta beriladi (administrator olib tashlagani qaytarilmaydi).
- Yangi rol: `hr_auditor`.
- Worker vazifalari: koordinator hisoboti (20:00), izoh muddati, attestatsiyani ochish (oy oxiri), ketish xavfi skaneri (dushanba), nazorat xulosasi (09:00), nomzodga Telegram xabari.

### O'zgardi
- Foydalanuvchi, `/employees` va `/branches` kabi API'lar o'zgarmadi; `GET /api/v1/meta` javobiga `plan` maydoni qo'shildi.
- Lavozim tanlash ro'yxatlarida "Bo'lim › Lavozim" ko'rsatiladi.
- Koordinator davomat muammolari va hisobotida faqat o'z filiallarini ko'radi.

### Buzuvchi o'zgarishlar
- **O'chirilgan modul API darajasida ham yopiladi:** `client.yaml → modules` da `false` bo'lgan (yoki tarifga kirmagan) modulning API yo'llari `403 module_disabled` qaytaradi (oldin faqat menyudan yashirilar edi).
- `/api/ext/*` yo'llari CSRF sarlavhasidan ozod (cookie yo'q, `X-API-Key` bilan himoyalangan).
- `client.yaml` ga ixtiyoriy `plan` va `license` kalitlari qo'shildi (sxema yangilandi). `plan` yozilmasa hech qanday cheklov yo'q.

## [1.0.0] — Xavfsizlik va chiqarish (F30)

### Qo'shildi
- Xavfsizlik: IP bo'yicha chastota cheklovi (nginx + Redis), CSP va xavfsiz sarlavhalar, gateway da soxtalashtirib bo'lmaydigan mijoz IP, production da zaif sirlar bilan ishga tushmaslik, `/api/docs` productionda yopiq, Excel/CSV formula-injection himoyasi (barcha eksportlar).
- Testlar: barcha endpointlar uchun avtomatik avtorizatsiya va CSRF supurishi, cheklov, sarlavhalar, injection, metrikalar (`tests/test_security.py`).
- Monitoring: `/api/metrics` (Prometheus, Redis-yig'ma), `--profile monitoring` (Prometheus, Grafana, ogohlantirish qoidalari), `watchdog.sh`, `make doctor`.
- Yuk testi (`make loadtest`), `WEB_CONCURRENCY` (API standart 3 jarayon).
- Hujjatlar: `SECURITY.md`, `RUNBOOK.md`, `LOADTEST.md`, `RELEASE.md`; tiklash mashqi natijalari.

### O'zgardi
- `GATEWAY` `X-Forwarded-For` ni `$remote_addr` bilan almashtiradi (oldin mijoz yuborgan qiymatga qo'shardi: IP soxtalashtirish mumkin edi).

### Buzuvchi o'zgarishlar
- Productionda `SECRET_KEY` (>=32 belgi), `MINIO_ROOT_PASSWORD` va standart bo'lmagan DB paroli **majburiy**: aks holda API ishga tushmaydi.
- `/api/docs` va `/api/openapi.json` productionda o'chiq (`API_DOCS=true` bilan yoqiladi).

## [0.29.0] — Migratsiya (F29)

### Qo'shildi
- `/migration`: xodimlar va davomat tarixini CSV/Excel dan import (ustun moslashtirish, shablonlar, dry-run, orqaga qaytarish), eski ID bog'lash.
- Nazorat summalari bilan jonli solishtirish (`/migration/reconcile`).
- Jadvallar: `migration_batches`, `migration_mappings`, `migration_legacy_ids`, `migration_checks`; `employees` va `attendance_records` da `import_batch_id`. Ruxsat `migration.manage`, modul `migration`.
- Hujjat: `docs/MIGRATION.md`.

### Buzuvchi o'zgarishlar
- Yo'q.

## [0.28.0] — Mijoz paketi (F28)

### Qo'shildi
- `client.yaml` sxemasi (`clients/client.schema.json`) va validator: `make validate-client`, ishga tushishda log.
- `deploy/scripts/new-client.sh` to'liq: skelet (`clients/_template`), `--domain`, `--env`, `--off`, brend ranglari, host nginx, sxema tekshiruvi.
- Zaxira/tiklash: `backup.sh`, `restore.sh` (`--verify` bilan zaxirani ishlayotgan bazaga tegmay tekshirish), AES-256 shifrlash, S3 nusxa; `upgrade.sh`.
- Extension hodisalari: `employee.created`, `employee.dismissed`, `ticket.created`.
- Hujjatlar: `docs/NEW-CLIENT.md`, `CLIENT-YAML.md`, `EXTENSIONS.md`, `BACKUP.md`, `UPGRADE.md`.
- LiveKit portlari sozlanadi (`LIVEKIT_TCP_PORT`, `LIVEKIT_UDP_PORT`), `COMPOSE_PROJECT_NAME` bilan bir serverda bir nechta mijoz.

### O'zgardi
- `make smoke` `.env` dagi `GATEWAY_PORT` ni o'qiydi.

### Buzuvchi o'zgarishlar
- Yo'q. (`client.yaml` dagi noma'lum kalitlar endi `validate-client` da xato; ishlash vaqtida avvalgidek e'tiborsiz qoldiriladi.)

## [0.1.0 – 0.27] — F0–F27

Core fazalari: autentifikatsiya va rollar, tashkiliy tuzilma, xodimlar, grafik va davomat, Face ID, so'rovlar, jarimalar, topshiriqlar, apteka tarmog'i, ehtiyojlar, checklistlar, nomzodlar, stajirovka, moliya, Abet, logistika, omborxona, ko'chma kuzatuv, resepshin va AyTi, qo'ng'iroqlar (LiveKit), AI va qidiruv, hisobotlar markazi. Tafsilot: `PLAN.md`, `README.md`.
