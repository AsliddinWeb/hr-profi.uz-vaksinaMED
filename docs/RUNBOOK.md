# Ekspluatatsiya qo'llanmasi (runbook)

Hamma buyruq loyiha ildizidan (`/opt/vaksina`). `make doctor` — umumiy tekshiruv; `make logs` — loglar.

## Kundalik / haftalik

| Davr | Nima | Qanday |
|---|---|---|
| Doimiy | Kuzatuvchi (har 5 daq) — muammo bo'lsa Telegramga xabar | cron: `*/5 * * * * cd /opt/vaksina && deploy/scripts/watchdog.sh` (`.env`: `ALERT_TELEGRAM_CHAT_ID`) |
| Kunlik 02:00 | Zaxira | cron: [BACKUP.md](BACKUP.md) |
| Haftalik | Zaxirani **tiklab tekshirish** | `make verify-backup FILE=<oxirgi arxiv>` → "ZAXIRA YAROQLI" |
| Haftalik | `make doctor` ni ko'rish (⚠ lar) | |
| Oylik | Bog'liqlik auditi, OS yangilanishlari, disk, sertifikat | `pip-audit`, `npm audit --omit=dev`, `apt upgrade`, `certbot renew --dry-run` |
| Choraklik | Tiklash mashqi (yangi serverga) | [BACKUP.md](BACKUP.md) "Tiklash mashqi" |

## Monitoring

- `GET /api/health/ready` (db, redis, worker) — tashqi uptime xizmatiga ulash mumkin (UptimeRobot va h.k.): `https://<domen>/api/health/ready`.
- Prometheus (ixtiyoriy): `docker compose --profile monitoring up -d` → Prometheus `127.0.0.1:9090`, Grafana `127.0.0.1:3000` (SSH tunnel: `ssh -L 3000:127.0.0.1:3000 server`). `.env`: `GRAFANA_PASSWORD`. Ogohlantirish qoidalari: `deploy/monitoring/alerts.yml` (ApiDown, DbDown, RedisDown, WorkerStale, QueueBacklog, High5xxRate, SlowApi, RateLimitSpike).
- Metrikalar: `vaksina_http_requests_total`, `vaksina_http_request_duration_seconds`, `vaksina_worker_heartbeat_age_seconds`, `vaksina_queue_depth`, `vaksina_users_active`, `vaksina_ws_connections`, `vaksina_rate_limited_total`. `/api/metrics` tashqaridan yopiq (nginx 404); `METRICS_TOKEN` berilsa Bearer bilan.

## Muammolar

| Alomat | Tekshirish | Yechim |
|---|---|---|
| Sayt ochilmaydi / 502 | `docker compose ps`, `make logs` | `docker compose up -d`; api migratsiyada qotgan bo'lsa `docker compose logs api` |
| API ishga tushmaydi: "Production sozlamalari xavfsiz emas" | log | `.env` dagi zaif sirni almashtiring (`make doctor`) |
| `worker: no-heartbeat` (jarima, eslatma, hisobot, SLA ishlamayapti) | `docker compose logs worker` | `docker compose restart worker`; Redis ishlayaptimi |
| Telegram xabarlari kelmayapti | `TELEGRAM_BOT_TOKEN`, `docker compose logs bot worker` | token, foydalanuvchi botni bloklamaganmi (avtomatik uziladi) |
| 429 ko'p (filialdan) | Prometheus `RateLimitSpike`, log `rate limit:` | bir IP ortida ko'p foydalanuvchi: `RATE_LIMIT_MULTIPLIER=2` |
| Qo'ng'iroq ulanmaydi (NAT ortida) | `LIVEKIT_NODE_IP`, 7881/tcp 7882/udp ochiqligi | `.env`, `ufw allow`, `docker compose up -d livekit` |
| Disk to'ldi | `df -h`, `docker system df` | `backups/` ni tozalang (`--keep`), `docker image prune`, MinIO hajmi |
| Sekin ishlamoqda | Prometheus SlowApi; `docker stats` | `WEB_CONCURRENCY`, DB `pg_stat_activity`, [LOADTEST.md](LOADTEST.md) |
| Ma'lumot buzildi/o'chib ketdi | | [BACKUP.md](BACKUP.md): `make restore` |

## Sirlarni almashtirish

| Sir | Oqibat | Tartib |
|---|---|---|
| `POSTGRES_PASSWORD` | — | DB da `ALTER USER`, `.env`, `docker compose up -d` |
| `MINIO_ROOT_PASSWORD` | — | MinIO da almashtirib `.env`, qayta ishga tushirish |
| `SECRET_KEY` | **Barcha sessiyalar bekor** (hamma qayta kiradi); `FACE_ENCRYPTION_KEY` alohida bo'lmasa Face shablonlari **o'qilmaydi** | avval `FACE_ENCRYPTION_KEY` ni eski `SECRET_KEY` qiymatiga qo'ying (alohida kalit qiling), keyin `SECRET_KEY` ni almashtiring |
| `FACE_ENCRYPTION_KEY` | Shablonlar o'qilmaydi | almashtirmang; kerak bo'lsa xodimlar qayta ro'yxatdan o'tadi |
| `LIVEKIT_API_SECRET` | Faol qo'ng'iroqlar uziladi | `.env` + `docker compose up -d livekit api` |
| `BACKUP_PASSPHRASE` | Eski arxivlar eski parol bilan ochiladi | eskisini saqlang |
| Foydalanuvchi paroli chiqib ketdi | | Foydalanuvchilar → parolni qayta o'rnatish (sessiyalar bekor) |

Har o'zgarishdan keyin: `make doctor`.

## Sozlash ko'rsatkichlari

`WEB_CONCURRENCY` (API jarayonlari, standart 3), `RATE_LIMIT_MULTIPLIER`, `METRICS_TOKEN`, `API_DOCS`, `LIVEKIT_*`, `BACKUP_PASSPHRASE`, `S3_*`, `ALERT_TELEGRAM_CHAT_ID`, `GRAFANA_PASSWORD` — hammasi `.env.example` da izoh bilan.
