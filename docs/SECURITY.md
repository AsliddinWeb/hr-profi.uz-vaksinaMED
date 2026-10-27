# Xavfsizlik: pentest checklist va nazorat

Holat: ✅ avtomatik testlar bilan tekshiriladi (`make test` → `tests/test_security.py` va modul testlari), 🔎 qo'lda/skript bilan tekshirilgan, ⚠ mijoz tomonida sozlanadi yoki ma'lum cheklov.

## 1. Kirish nazorati (OWASP A01)

| Nazorat | Qanday tekshiriladi | Holat |
|---|---|---|
| Har bir himoyalangan endpoint tokensiz 401/403 qaytaradi (300+ endpoint, OpenAPI dan avtomatik supurish; yangi endpoint avtomatik qamraladi) | `test_every_non_public_endpoint_rejects_anonymous` | ✅ |
| Ochiq endpointlar ro'yxati qat'iy: login, refresh, health, meta, LiveKit webhook (JWT imzo), metrics (ichki), shaxsiy havolali jamoat sahifalari | `PUBLIC` ro'yxati testda | ✅ |
| Rol/ruxsat bo'yicha cheklov (RBAC wildcard, modul bo'yicha `*.own/read/manage`) va ob'ektga egalik (IDOR): boshqa foydalanuvchi yozuvi 404 | har modul testlari (`test_needs`, `test_desk`, `test_calls`, `test_tasks`, ...) | ✅ |
| WebSocket: cross-site hijacking (Origin) va sessiya qayta tekshiruvi | `test_ws_unit` | ✅ |
| Oxirgi Ta'sischini o'chirib/o'chirib qo'yib bo'lmaydi; o'zini bloklash taqiqlangan | `test_users_rbac` | ✅ |

## 2. Autentifikatsiya va sessiya (A07)

| Nazorat | Holat |
|---|---|
| Parol Argon2id; kuchsiz parol rad etiladi (qisqa, faqat raqam/harf, login bilan bir xil); vaqtinchalik parol birinchi kirishda almashtiriladi | ✅ `test_auth`, `test_users_rbac` |
| Login urinish cheklovi (login+IP bo'yicha Redis, 429 `too_many_attempts`), muvaffaqiyatsiz va bloklangan urinishlar auditga | ✅ `test_auth` |
| Login vaqti mavjud/mavjud bo'lmagan foydalanuvchi uchun bir xil (soxta hash bilan solishtirish) va bir xil xato kodi | ✅ |
| Access token 15 daq, refresh 30 kun, **refresh faqat hash** ko'rinishida saqlanadi, aylantiriladi; parol almashtirilganda boshqa sessiyalar bekor | ✅ |
| Cookie: `HttpOnly`, `SameSite=Lax`, HTTPS da `Secure`; refresh cookie faqat `/api/auth` yo'lida | ✅ `test_auth_cookies_are_httponly_and_scoped` |
| JWT algoritmi qat'iy (HS256), `alg=none` qabul qilinmaydi | 🔎 |

## 3. CSRF, XSS, injection (A03)

| Nazorat | Holat |
|---|---|
| Barcha o'zgartiruvchi so'rovlar (POST/PUT/PATCH/DELETE) `X-Requested-With` ni talab qiladi (cross-site forma bu headerni qo'sha olmaydi); istisno faqat imzolangan LiveKit webhook | ✅ `test_mutating_endpoints_require_csrf_header` (barcha endpointlar) |
| SQL: faqat ORM/parametrli so'rovlar; `ILIKE` qidiruvda `%`/`_`/`\` himoyalangan; injection satrlari bilan sinov | ✅ `test_injection_strings_are_inert`, `test_global_search_...` |
| XSS: React matnni escape qiladi; `dangerouslySetInnerHTML` faqat 2 joyda va faqat serverda `segno` yaratgan QR SVG uchun (foydalanuvchi matni emas); **CSP** gateway da: `script-src 'self'`, `object-src 'none'`, `frame-ancestors 'self'`, `base-uri 'self'` | 🔎 (brauzerda asosiy sahifalar CSP buzilishsiz) |
| **Excel/CSV formula injection**: bazadagi `=`, `+`, `-`, `@` bilan boshlangan matn eksportda formula bo'lmaydi (7 ta Excel eksport + CSV) | ✅ `test_spreadsheet_formula_injection...`, `test_exports_neutralise_hostile_names` |
| Fayl yuklash: hajm limiti, **haqiqiy tur (magic bytes)** tekshiruvi, kalit serverda yaratiladi (path traversal yo'q), yuklab olishda `nosniff` + `attachment` | ✅ `test_employees`, `test_needs` (fayl testlari) |
| Prompt injection (AI): foydalanuvchi matni `<data>` ichida "ma'lumot", ichki izohlar va nomzod ismi modelga yuborilmaydi, javob JSON si tekshirib normallashtiriladi | ✅ `test_ai` |

## 4. Chastota cheklovi va DoS (A04/A05)

| Qatlam | Cheklov | Holat |
|---|---|---|
| nginx gateway | `/api/` 60 so'rov/s (burst 200), `/api/auth/login` 30/daq (burst 10), IP bo'yicha 100 ulanish, sekin so'rov taymautlari | 🔎 |
| Ilova (Redis, IP bo'yicha, 1 daqiqalik oyna) | umumiy 3000/daq; auth 120; AI 90; qidiruv 240; eksport/PDF/hisobot 60; fayl/import 240 → `429 rate_limited` + `Retry-After`; Redis ishlamasa cheklov o'chadi (xizmat to'xtamaydi) | ✅ `test_rate_limit_*` |
| Login | login+IP bo'yicha qulflash (yuqorida) | ✅ |
| AI | foydalanuvchiga kunlik limit (sozlanadi) | ✅ |
| Fayl/qatorlar | import 25 MB, 20k/200k qator; nginx `client_max_body_size 50m` | ✅ |

Koeffitsiyent: `RATE_LIMIT_MULTIPLIER` (masalan filiallar bitta IP ortida bo'lsa oshiring), o'chirish: `RATE_LIMIT_ENABLED=false` (faqat yuk testi).

## 5. Sirlar va konfiguratsiya (A02/A05)

| Nazorat | Holat |
|---|---|
| **Production da zaif sirlar bilan API ishga tushmaydi**: `SECRET_KEY` (<32 belgi/standart), `MINIO_ROOT_PASSWORD`, standart DB paroli, qisqa LiveKit sirri → startup xatosi | ✅ `test_production_config_guard` |
| `make doctor` (`deploy/scripts/preflight.sh`): `.env` ruxsati 600, kuchli sirlar, gateway faqat 127.0.0.1, ufw, xizmatlar sog'lig'i, `/api/docs` va `/api/metrics` yopiqligi, zaxira yoshi, TLS muddati | 🔎 |
| OpenAPI hujjati (`/api/docs`) productionda o'chiq (`API_DOCS=true` bilan yoqiladi) | ✅ |
| Xavfsiz sarlavhalar: `nosniff`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`, `COOP`, API javoblari `Cache-Control: no-store`; HSTS host nginx da | ✅/🔎 |
| Mijoz IP si soxtalashtirib bo'lmaydi: gateway `X-Forwarded-For` ni `$remote_addr` bilan **almashtiradi** (real_ip eng o'ng ishonchsiz manzilni oladi), audit va cheklov shu IP ga tayanadi | 🔎 |
| Sirlar kodda yo'q; `.env` git ga kirmaydi; `.env.example` faqat nomlar | 🔎 |
| Bog'liqliklar: `pip-audit` — ma'lum zaiflik yo'q; `npm audit --omit=dev` — 0 zaiflik (har chiqarishdan oldin qayta ishga tushiring) | 🔎 |

## 6. Maxfiy ma'lumotlar

| Nazorat | Holat |
|---|---|
| Face ID shablonlari **shifrlangan** (alohida `FACE_ENCRYPTION_KEY`), rozilik yozuvi, saqlash muddati (365 kun, bo'shatilganda 30 kun), kirish jurnali | ✅ `test_face` |
| Trek (GPS) ni ko'rish auditga yoziladi, 90 kundan keyin o'chadi; xodim rozilikni qaytarib oladi | ✅ `test_mobile` |
| Audit jurnali: kim/qachon/nima (login, parol almashtirish, rol, import, eksport, yuklab olish, AI sozlamalari, migratsiya); jurnalni o'chiruvchi endpoint yo'q; maxfiy kalitlar `***` | ✅ |
| Zaxira shifrlash (AES-256, `BACKUP_PASSPHRASE`) va sha256 | ✅ [BACKUP.md](BACKUP.md) |
| AI ga yuboriladigan ma'lumot minimal (ichki izoh, nomzod ismi yuborilmaydi), so'rov matni saqlanmaydi, faqat token hisobi | ✅ |

## 7. Ma'lum cheklovlar / mijoz tomoni

- ⚠ **MFA (ikki bosqichli kirish) yo'q.** Parol + cheklov + sessiya nazorati bor; Ta'sischi hisoblari uchun kuchli parol va (tashqi) VPN/IP cheklash tavsiya etiladi. Keyingi versiya uchun reja.
- ⚠ Access token 15 daqiqa amal qiladi: sessiya bekor qilinganda eski token shu muddatgacha ishlashi mumkin (refresh darrov to'xtaydi).
- ⚠ Telegram bot xabarlari Telegram serverlari orqali o'tadi: maxfiy tafsilot (parol, hujjat raqami) xabarga yozilmaydi, faqat sarlavha/havola.
- ⚠ CSP da `img-src`/`connect-src` `https:` ruxsat etilgan (xarita tile serveri mijozga qarab o'zgaradi); qat'iy domen ro'yxati kerak bo'lsa `deploy/nginx/default.conf.template` da toraytiring.
- ⚠ Tashqi (mustaqil) pentest o'tkazilmagan: bu checklist ichki audit va avtomatik testlar. Katta mijozga topshirishdan oldin mustaqil pentest tavsiya etiladi.

## 8. Hodisaga javob (qisqa)

1. Shubhali kirish: Ta'sischi `Foydalanuvchilar` → sessiyalarni bekor qilish va parolni qayta o'rnatish; `audit` jurnalidan `auth.login*` ni ko'ring.
2. Sirlar chiqib ketgan bo'lsa: [RUNBOOK.md](RUNBOOK.md) "Sirlarni almashtirish".
3. Ma'lumot yo'qolishi/buzilishi: [BACKUP.md](BACKUP.md) bo'yicha tiklash.
