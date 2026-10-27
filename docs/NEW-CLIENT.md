# Yangi mijozni 1 soatda ko'tarish

Har mijoz uchun **alohida server (droplet), alohida baza, MinIO va `.env`**. Core kod hamma mijozda bir xil, farq faqat `clients/<nom>/` papkasida.

Kerak: Ubuntu 22.04+ droplet (4 GB RAM dan), domen (A yozuvi droplet IP siga), SSH.

| # | Qadam | Vaqt |
|---|---|---|
| 1 | DNS: `hr.mijoz.uz` → droplet IP | 5 daq (tarqalishini kuting) |
| 2 | Server tayyorlash: `sudo deploy/scripts/droplet-setup.sh` (docker, nginx, certbot, firewall: 80, 443, 7881/tcp, 7882/udp) | 5 daq |
| 3 | Kodni olish: `git clone <repo> /opt/vaksina && cd /opt/vaksina && git checkout <core-tag>` | 2 daq |
| 4 | Mijoz skeleti va `.env`: quyida | 3 daq |
| 5 | `make up` (build + migratsiya + ishga tushirish) | 5–10 daq |
| 6 | `make admin` — birinchi Ta'sischi, `make smoke` — tekshiruv | 2 daq |
| 7 | Host nginx + HTTPS: `clients/<nom>/host-nginx.conf` → `/etc/nginx/sites-available/<domen>`, symlink, `certbot --nginx -d <domen>` | 5 daq |
| 8 | Telegram bot (ixtiyoriy), AI kaliti (ixtiyoriy), zaxira cron va `watchdog.sh` cron ([RUNBOOK.md](RUNBOOK.md)) | 10 daq |
| 9 | Sozlash: brend, modullar, filial/bo'limlar, rollar, xodimlar importi | qolgan vaqt |

## 4-qadam: skelet va `.env`

```bash
deploy/scripts/new-client.sh acme "Acme HR" \
    --domain hr.acme.uz --node-ip 203.0.113.7 \
    --primary "#0f766e" --accent "#f97316" \
    --off logistics,warehouse --env
```

- `clients/acme/` yaratiladi (`client.yaml`, `backend_ext/`, `frontend_ext/`, `migrations/`, `.env.example`, `host-nginx.conf`), sxema bo'yicha tekshiriladi.
- `--env`: `.env` yaratiladi (tasodifiy `SECRET_KEY`, `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `LIVEKIT_API_SECRET`, `FACE_ENCRYPTION_KEY`), `chmod 600`. Mavjud `.env` ga tegilmaydi.
- `--node-ip`: LiveKit uchun serverning **ochiq IP si** (qo'ng'iroqlar NAT ortida ishlashi uchun shart).

> **`SECRET_KEY` va `FACE_ENCRYPTION_KEY` ni parol menejerida saqlang.** Ular yo'qolsa, zaxiradan tiklangan bazadagi Face ID shablonlari o'qilmaydi (xodimlar qayta ro'yxatdan o'tadi).

## Tekshiruv ro'yxati

- [ ] `make doctor` — ✘ yo'q (sirlar, tarmoq, xizmatlar, zaxira, sertifikat)
- [ ] `make smoke` — db, redis, worker `ok`, frontend 200
- [ ] `https://<domen>` ochiladi, brend va ranglar to'g'ri; `curl https://<domen>/api/v1/meta` da `client` = mijoz nomi
- [ ] `make admin` paroli bilan kirish va parolni almashtirish
- [ ] `.env`: `PUBLIC_URL=https://<domen>` (Telegram havolalari), `TELEGRAM_BOT_TOKEN` (ixtiyoriy), `ANTHROPIC_API_KEY` (ixtiyoriy)
- [ ] Qo'ng'iroq sinovi: ikki xil tarmoqdan (Wi-Fi va mobil internet) bir xonaga kirish; 7881/tcp va 7882/udp ochiqligi
- [ ] `make backup` + `make verify-backup FILE=backups/<arxiv>` → "ZAXIRA YAROQLI"; cron o'rnatilgan ([BACKUP.md](BACKUP.md))
- [ ] `.env` va `BACKUP_PASSPHRASE` ning nusxasi sizda (server tashqarisida)

## Mijozga moslashtirish

- Brend, modullar, vaqt mintaqasi: [CLIENT-YAML.md](CLIENT-YAML.md)
- Mijozga xos kod (router, hodisa, sahifa, jadval, worker): [EXTENSIONS.md](EXTENSIONS.md)
- Core yangilash: [UPGRADE.md](UPGRADE.md)

Bir serverda bir nechta mijoz kerak bo'lsa: har biriga alohida papka (`/opt/vaksina-<nom>`), `.env` da `COMPOSE_PROJECT_NAME`, `GATEWAY_PORT` va `LIVEKIT_TCP_PORT/LIVEKIT_UDP_PORT` ni farqlang. Tavsiya: baribir alohida server.
