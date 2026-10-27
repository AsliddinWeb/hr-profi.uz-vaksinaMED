# VaksinaHR — arxitektura va fazalar rejasi (v2)

## 1. Tasdiqlangan qarorlar

| # | Qaror |
|---|---|
| 1 | **Har mijoz uchun alohida deploy** (`client1.vaksinahr.uz`, ...). Asos (core) bitta, mijozga xos kod **extension** sifatida ajratiladi. Multi-tenant yo'q, `tenant_id` yo'q. Har mijozning o'z DB si, o'z MinIO si, o'z `.env` i. |
| 2 | HTTPS: DigitalOcean + **certbot** (host nginx, 443). Konteynerlar ichida TLS yo'q. |
| 3 | Qo'ng'iroq: **LiveKit** (o'z serverimizda). Qo'shimcha portlar ochiladi (pastda). |
| 4 | Face ID: **serverda**, InsightFace + pgvector + liveness, rozilik yozuvi bilan. |
| 5 | Logistika: **core ichidagi modul** (alohida tizim emas). Telefon (PWA) GPS birinchi, apparat trekerlar keyin (Traccar ixtiyoriy). |
| 6 | MVP yo'q, **to'liq ishlaydigan tizim**. Fazalar kichik bo'laklarga bo'lingan, har faza oxirida ishlaydigan va test qilingan natija. |

## 2. Servislar (Docker Compose)

Tashqi kirish: host nginx `443 (TLS, certbot)` -> `127.0.0.1:6788` (gateway). Qolgan hamma servis ichki tarmoqda.

| Servis | Texnologiya | Izoh |
|---|---|---|
| gateway | **nginx** (Caddy emas, chunki certbot ishlatiladi) | 6788 ichki kirish: `/` frontend, `/api`, `/ws`, `/livekit`, `/files`, `/tiles` |
| frontend | React + Vite + TS, Tailwind + shadcn/ui, TanStack Query/Router, ECharts, MapLibre | PWA, UZ/RU, light (asosiy) + dark |
| api | FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2 | JWT (httpOnly cookie) + RBAC + audit |
| db | PostgreSQL + **pgvector** | yuz embeddinglari. Geofence (100 m) oddiy haversine formulasi bilan, PostGIS kerak emas |
| redis | Redis | navbat, kesh, pub/sub (jonli kuzatuv), rate-limit |
| worker | arq | jarima hisobi, eskalatsiya, hisobotlar, PDF/Excel, importlar |
| scheduler | arq cron (workerning ichida) | alohida konteyner kerak emas |
| pdf | Gotenberg | xat, hisobot PDF |
| storage | MinIO | rasm, skan, video, yuz fotolari, PMTiles xarita fayli |
| face | FastAPI + InsightFace (ichki servis) | embedding, liveness, matching |
| bot | aiogram | Telegram hisobot va bildirishnomalar |
| calls | LiveKit server | audio/video/ekran, ichki TURN |
| backup | pg_dump + mc (cron) | kunlik zaxira, tashqi S3 ga |
| monitoring (ixtiyoriy) | Prometheus, Grafana, GlitchTip | |

**Ochiladigan tashqi portlar** (DO firewall): `80, 443` (nginx/certbot), `7881/tcp` (LiveKit TCP fallback), `7882/udp` (LiveKit media, bitta UDP port), `3478/udp` (TURN, ixtiyoriy). Ilova trafigi faqat 443 -> 6788.

**Xarita:** o'zbekiston OSM extract -> **PMTiles** faylini MinIO/gateway orqali o'zimiz beramiz. Tashqi tile serverga bog'liq emasmiz.

## 3. Mijozga moslashtirish (extension) tizimi

```
core/                  # umumiy kod (git tag bilan versiyalanadi)
  backend/app/...
  frontend/src/...
clients/
  client1/
    client.yaml        # modul yoqish/o'chirish, brend, rollar, qoidalar
    backend_ext/       # qo'shimcha routerlar, modellar, vazifalar (entry point bilan yuklanadi)
    frontend_ext/      # sahifa/komponent override (build-time alias)
    migrations/        # faqat shu mijozning jadvallari (alohida alembic branch)
    .env.example
deploy/
  compose.base.yml
  compose.client.yml   # mijozga xos override
  new-client.sh        # yangi mijoz skeleti
```

- Core o'zgarsa: tag chiqariladi, mijozlar o'z vaqtida `core@vX` ga o'tadi.
- Extension core jadvallarini o'zgartirmaydi, faqat o'z jadvallarini qo'shadi, hook/event orqali ulanadi.
- Feature-flag: modullar `client.yaml` da yoqiladi (masalan, logistika ba'zi mijozda yo'q).

## 4. Dizayn yo'nalishi

`ui/namuna1.webp` asosida: och lavanda fon, yumshoq oq kartalar (20-24px radius), pastel gradient KPI, bitta urg'u rangi (brend ko'k + orange), tekis sidebar (1 daraja, rolga qarab filtrlangan), qora asosiy tugma. Dark mode ixtiyoriy. Barcha rang va oraliqlar **design tokenlar** (CSS variables) orqali, mijoz o'z brendini `client.yaml` dan oladi.

## 5. Fazalar

Har fazaning oxirida: ishlaydigan funksiya + testlar + docker-compose da ishga tushadi + hujjat.

| Faza | Mazmun | Tayyor mezoni |
|---|---|---|
| **F0 Poydevor** (TAYYOR) | Monorepo, compose, gateway, CI, `.env` boshqaruvi, Alembic, extension mexanizmi, `new-client.sh`, deploy skripti (DO + certbot), design tokenlar, UI kit, i18n UZ/RU, PWA skeleti | `docker compose up` -> bo'sh app 6788 da ishlaydi, health-check, birinchi deploy staging ga |
| **F1 Auth va rollar** (TAYYOR) | Login, JWT/refresh, parol siyosati, sessiyalar, RBAC (rol va ruxsat matritsasi), audit log, profil, til/tema, login/parol avtogeneratsiya | Rollar bo'yicha menyu va API himoyasi, audit yozuvlari |
| **F2 Bildirishnoma va realtime** (TAYYOR) | In-app bildirish, WebSocket, Telegram bot ulash, shablonlar, o'qilgan/o'qilmagan | Bitta voqea -> app + Telegram da chiqadi |
| **F3 Tashkiliy tuzilma** (TAYYOR) | Bo'limlar, lavozimlar, filiallar (geo), org-chart (o'qiladigan), boshliq tayinlash | Daraxt tahrirlanadi, filial xaritada |
| **F4 Xodimlar** (TAYYOR) | Karta, tarix, hujjatlar, Excel import/eksport, dublikat nazorati, faol/nofaol, ommaviy amallar | 500 xodim importi, qidiruv/filtr tez |
| **F5 Smena va grafik** (TAYYOR) | Smena turlari (tungi/erkin ham), guruhlar, grafik, bayramlar, ofis/dorixona/ombor qoidalari | Har xodimga grafik hisoblanadi |
| **F6 Davomat yadrosi** (TAYYOR) | Keldi/ketdi (QR, GPS geofence), kech/erta hisobi, tabel, qo'lda tuzatish (audit bilan), kunlik/hafta/oy hisobot | Tabel hisobi qo'lda hisoblangan natija bilan mos |
| **F7 Face ID** (TAYYOR) | Ro'yxatga olish, liveness, matching, rozilik, saqlash muddati, adminga ko'rish huquqi | FAR/FRR o'lchovi, biometrik ma'lumot shifrlangan |
| **F8 Davomat dashboard** (TAYYOR) | Tahlil, kesimlar (bo'lim/filial), top/kechikuvchilar, PDF eksport, davrlar | Dashboard raqamlari bitta manbadan (nomuvofiqlik yo'q) |
| **F9 Javob olish** (TAYYOR) | Kunlik/soatlik so'rov, koordinator -> HR eskalatsiya (8 soat), tasdiq/rad, kalendar, tarix, Telegram | Eskalatsiya vaqti testlangan |
| **F10 Tushuntirish xatlari** (TAYYOR) | Xat shabloni, imzo, QR tekshirish, PDF (Gotenberg), skaner, holatlar | Hujjat QR orqali tekshiriladi |
| **F11 Jarimalar** (TAYYOR) | 6 bosqichli qoidalar (sozlanadigan), avtomatik hisob, tasdiq/bekor, blok, hisobot | Qoida o'zgarsa, tarix buzilmaydi; qo'lda tekshiruv tasdiqli |
| **F12 Topshiriqlar** (TAYYOR) | Kanban, kalendar, ro'yxat, chat, fayl, tarix, shablon, deadline, tahlil | Oqim to'liq, tahlil to'g'ri |
| **F13 Eslatmalar** (TAYYOR) | Eslatma, takrorlanish, Telegram/in-app | Vaqtida ishlaydi |
| **F14 Apteka tarmog'i** (TAYYOR) | Filial kartalari, mudir/farmasevt/stajyor, jamoa holati, ommaviy xarita, "xodim kerak" | 142 filial ma'lumoti to'g'ri |
| **F15 Ehtiyojlar** (TAYYOR) | 4 bosqichli oqim (so'rash -> ijrochi -> bajarish -> tasdiq), statuslar, muddat | Barcha bosqich hodisalari auditda |
| **F16 Koordinator checklist** (TAYYOR) | Filialga borish (GPS), checklist shablonlari, ball, reyting, filial qamrovi, trendlar | Ball hisobi tekshirilgan |
| **F17 Nomzodlar va ish o'rinlari** (TAYYOR) | Vakansiya, ariza, nomzod pipeline, rekruter, izoh, AI to'ldirish | Nomzod -> xodimga aylantirish |
| **F18 Stajirovka (preboarding)** (TAYYOR) | Bosqichlar (video/PDF), testlar, ball, progress, "ishga tayyor" | Stajyor oqimi oxirigacha |
| **F19 Moliya: oylik** (TAYYOR) | Fiks, savdo, reja, bonus, KPI, avans, jarima integratsiyasi, hisob-kitob, eksport | Hisob qo'lda tekshiruv bilan mos |
| **F20 Abet** (TAYYOR) | Menyu, baholash, QR, tahlil, izohlar | |
| **F21 Logistika** (TAYYOR; haqiqiy yo'ldagi sinov kutilmoqda) | Mashina, haydovchi, hujjat muddati, jonli GPS xarita, reys, yoqilg'i normasi va hisobi, GPS davomat, hisobotlar | Telefon PWA GPS bilan haqiqiy yo'lda sinov |
| **F22 Omborxona** (TAYYOR) | Erkin grafik (08:00 -> 07:00), xodimlar, nazorat, holat | |
| **F23 Ko'chma davomat va jonli kuzatuv** (TAYYOR; telefonda haqiqiy sinov kutilmoqda) | Ruxsat berilgan xodimlar, trek, xarita, xavfsizlik hodisalari | Batareya va ruxsat holati hisobga olingan |
| **F24 Resepshin va AyTi** | Mehmon qaydi, ariza/ticket, statuslar | (TAYYOR) |
| **F25 Qo'ng'iroqlar** | LiveKit: admin bilan audio/video, konferensiya, ekran ulashish, tarix | Turli tarmoqda (mobil/NAT) sinov (TAYYOR; haqiqiy NAT sinovi kutilmoqda) |
| **F26 AI va qidiruv** | AI xulosa (Claude API), AI to'ldirish, global qidiruv | (TAYYOR; haqiqiy API kaliti bilan sinov kutilmoqda) |
| **F27 Hisobotlar markazi** | Jadvalli Excel/PDF/Telegram hisobotlar, sozlamalar | (TAYYOR; Telegramga fayl yuborish haqiqiy bot bilan sinov kutilmoqda) |
| **F28 Mijoz paketi** | `new-client.sh` to'liq, client.yaml sxemasi, extension misoli, upgrade qo'llanmasi, backup/restore | Yangi mijoz 1 soatda ko'tariladi (TAYYOR; haqiqiy serverda sinov kutilmoqda) |
| **F29 Migratsiya** | Eski tizimdan xodim/tarix/ma'lumot import, solishtirish | Eski va yangi raqamlar mos (TAYYOR; haqiqiy eski tizim fayli bilan sinov kutilmoqda) |
| **F30 Xavfsizlik va chiqarish** | Pentest checklist, rate-limit, yuk testi, restore mashqi, monitoring, hujjat, production release | Barcha test yashil, zaxira tiklandi (TAYYOR) |
| **F31 Interfeys** | Qayta qurilgan UI (neytral palitra, yon panel, filtrlar) | (TAYYOR) |
| **F32 Davomat ishonchliligi** | Davomat muammosi so'rovi (koordinator → HR → avtomatik tuzatish), ketishni tasdiqlash, Face ID yordami | (TAYYOR) |
| **F33 Koordinator hisoboti** | Koordinator × smena hisoboti, sabab va chora izohi, 20:00 avtomatik yuborish | (TAYYOR) |
| **F34 Zayafka → e'lon → manba** | Zayafka tasdig'i, vakansiya avtomatik, lavozim talablari, kanallar, shaxsiy havolalar, ommaviy ariza | (TAYYOR) |
| **F35 Nomzod kirishi** | Telegram bot, suhbat va tajriba darajasi, fon tekshiruv, AI skaner, job offer, rekruter paneli | (TAYYOR; haqiqiy bot va AI kaliti bilan sinov kutilmoqda) |
| **F36 Preboarding/onboarding** | Filial paketi, 7 kunlik hisobot va qaror, oflayn darslar, kadrovik | (TAYYOR) |
| **F37 Attestatsiya va o'sish** | Oylik attestatsiya, yig'ma baho, zinapoya, o'sish takliflari | (TAYYOR) |
| **F38 Ushlab qolish va nazorat** | Ketish xavfi, haftalik uchrashuv, offboarding, nazorat paneli, HR auditor | (TAYYOR) |
| **F39 KOSHI tariflari** | START/PRO/PREMIUM, o'rin va litsenziya, tarif sahifasi | (TAYYOR) |
| **F40 Integratsiyalar** | API kalitlari, tashqi API (savdo/reja), filial solishtirish, shikoyatlar | (TAYYOR; Kaizen, gamifikatsiya, HR byudjeti, GPP shablonlari rejada) |

## 6. Texnik tamoyillar

- API-first, OpenAPI dan TS klient avtomatik generatsiya.
- Pul (so'm) va vaqt hisoblari serverda, `Decimal`, UTC saqlash, Asia/Tashkent ko'rsatish.
- Har o'zgarish (davomat tuzatish, jarima, oylik) audit logga yoziladi.
- Shaxsiy ma'lumot va biometrika: shifrlash, rozilik, saqlash muddati, kirish jurnali.
- Testlar: pytest (API), Playwright (asosiy oqimlar), hisob-kitoblar uchun alohida unit testlar.
