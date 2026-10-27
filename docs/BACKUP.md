# Zaxira va tiklash

Zaxira = **PostgreSQL (`pg_dump -Fc`) + MinIO fayllari (rasm, hujjat, skan) + manifest** (`client`, versiya, migratsiya revizyalari, sanoqlar) bitta arxivda. Skriptlar loyiha ildizidan ishlaydi va `.env` ni o'zi o'qiydi.

```bash
make backup                          # backups/<mijoz>-<sana>.tar.gz (+ .sha256), 14 ta saqlanadi
make backup ARGS="--keep 30 --with-env"
make verify-backup FILE=backups/acme-20261110-020000.tar.gz   # ishlayotgan bazaga TEGMAYDI
make restore FILE=backups/acme-....tar.gz                      # HAQIQIY tiklash (mijoz nomini yozib tasdiqlanadi)
```

## Tekshirish (har hafta!)

`verify-backup` arxivni **vaqtinchalik bazaga** (`<db>_verify`) tiklaydi, xodimlar soni, migratsiya revizyasi va fayllar sonini manifest bilan solishtiradi va bazani o'chiradi. Natija `ZAXIRA YAROQLI` bo'lmasa — zaxira yo'q deb hisoblang. Tekshirilmagan zaxira zaxira emas.

## Cron (kunlik, 02:00) + haftalik tekshiruv

```cron
0 2 * * *  cd /opt/vaksina && deploy/scripts/backup.sh --keep 30 >> /var/log/vaksina-backup.log 2>&1
30 3 * * 0 cd /opt/vaksina && deploy/scripts/restore.sh "$(ls -1t backups/*.tar.gz* | grep -v sha256 | head -1)" --verify >> /var/log/vaksina-backup.log 2>&1
```

## Sirlar va shifrlash

- Arxivda **`.env` yo'q** (standart). Uni alohida, xavfsiz joyda saqlang. `SECRET_KEY` va `FACE_ENCRYPTION_KEY`siz tiklangan Face ID shablonlari o'qilmaydi va sessiyalar bekor bo'ladi.
- `--with-env` `.env` ni arxivga qo'shadi: **faqat `BACKUP_PASSPHRASE` bilan shifrlangan holda** saqlang/yuboring.
- `.env` da `BACKUP_PASSPHRASE=...` bo'lsa arxiv AES-256 (PBKDF2) bilan shifrlanadi (`.tar.gz.enc`); tiklashda shu parol kerak. Parolni yo'qotsangiz arxivni ochib bo'lmaydi.

## Tashqi nusxa (server o'chib qolsa ham)

`.env` da `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` berilsa, har zaxira shu yerga ham yuklanadi (DigitalOcean Spaces, AWS S3, MinIO). Mahalliy nusxa baribir saqlanadi. **Kamida bitta nusxa serverdan tashqarida bo'lsin.**

## Yangi serverga ko'chirish

1. Yangi serverda: [NEW-CLIENT.md](NEW-CLIENT.md) 1–3 qadamlar; `.env` ni **eski `.env` nusxasidan** qo'ying (kalitlar bir xil!).
2. `make up` (bo'sh bazada ham ko'tariladi), so'ng `make restore FILE=<arxiv> ARGS=--yes`.
3. DNS ni yangi IP ga o'tkazing, certbot, `LIVEKIT_NODE_IP` ni yangilang.

Tiklashdan keyin api qayta ishga tushadi va migratsiyalar joriy kod versiyasigacha avtomatik qo'llanadi (zaxira eski versiyadan bo'lsa ham). Arxivdagi mijoz (`manifest.client`) va ishlayotgan `CLIENT_NAME` bir xil bo'lishi kerak: mijoz migratsiya revizyalari mos kelmasa api ko'tarilmaydi.

## Nimani tiklamaydi

Redis (navbat/kesh: qayta to'ladi), `.env`, host nginx va sertifikatlar, LiveKit holati (qo'ng'iroqlar tarixi bazada, faol xonalar emas).

## Tiklash mashqi (yangi serverga) — natijalar

Mashq tartibi (har chorakda): (1) manba serverda `make backup` (`--with-env` faqat mashq uchun), (2) **toza** nusxada (yangi papka, boshqa loyiha nomi va portlar) `.env` ni arxivdan olib `make up`, (3) `deploy/scripts/restore.sh <arxiv> --yes`, (4) tekshirish: har jadval qatorlari soni, `users` jadvali parol hashlari, MinIO fayllari soni manba bilan bir xil bo'lsin.

**F30 mashqi (2026-10-26, lokal Docker):** manba — 93 jadval, 8 xodim, 63 fayl (MinIO). Toza stek 19 s da ko'tarildi (imidjlar keshda; haqiqiy serverda build 5–10 daq), tiklash **10 s**. Natija: **93 jadvalning hammasida qatorlar soni mos**, `users` (login + parol hash) kontrol yig'indisi mos, MinIO 63/63 fayl mos, API `meta` to'g'ri mijozni qaytardi. Topilgan va hujjatlashtirilgan nuqta: `.env` da bir kalit ikki marta bo'lsa Compose **birinchisini** oladi — nusxa `.env` ga port qo'shishdan oldin eski satrni olib tashlang.
