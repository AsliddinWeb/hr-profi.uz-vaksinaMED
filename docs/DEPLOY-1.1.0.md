# v1.1.0 ni serverga qo'yish (F32–F40)

Arxiv: `make pack` → `dist/vaksinahr-1.1.0.tar.gz` (+ `.sha256`). Sirlar (`.env`), zaxira va keshlar arxivda yo'q.
Tekshirilgan: backend testlar, frontend lint/tip/testlar, migratsiyalar `0028 → 0036` va orqaga (to'ldirilgan baza nusxasida), `make smoke`.

## A. Mavjud serverni yangilash (tavsiya etilgan yo'l)

```bash
# 1. Mahalliy mashinadan arxivni yuborish
scp dist/vaksinahr-1.1.0.tar.gz dist/vaksinahr-1.1.0.tar.gz.sha256 user@server:/tmp/

# 2. Serverda: yaxlitlikni tekshirish, ZAXIRA, kodni almashtirish
cd /tmp && sha256sum -c vaksinahr-1.1.0.tar.gz.sha256
cd /opt/vaksina && make backup                       # zaxira nomini yozib oling
mkdir /opt/vaksina-new && tar -xzf /tmp/vaksinahr-1.1.0.tar.gz -C /opt/vaksina-new
cp .env /opt/vaksina-new/.env && chmod 600 /opt/vaksina-new/.env
cp -r clients/<CLIENT_NAME> /opt/vaksina-new/clients/ 2>/dev/null   # mijozga xos papka bo'lsa
# eski papkani saqlab, yangisini almashtiring: mv /opt/vaksina /opt/vaksina-old && mv /opt/vaksina-new /opt/vaksina

# 3. Ishga tushirish (migratsiyalar 0029–0036 api startida o'zi qo'llanadi)
cd /opt/vaksina && make up
make smoke && make doctor
```

Agar server git bilan ishlasa: kodni repozitoriyga qo'yib `make upgrade TAG=v1.1.0` ([UPGRADE.md](UPGRADE.md)).
**Orqaga qaytarish:** `make restore FILE=backups/<arxiv>` va eski kod papkasi ([UPGRADE.md](UPGRADE.md), [BACKUP.md](BACKUP.md)).

## B. Yangi server (birinchi marta)

[NEW-CLIENT.md](NEW-CLIENT.md) bo'yicha (droplet, domen, `new-client.sh --env`, `make up`, `make admin`, host nginx + certbot).
KOSHI mijozi uchun namuna: `clients/koshi/client.yaml` (PRO tarif, 50 o'rin).

## Ishga tushgandan keyin (majburiy)

1. **`.env`:** `PUBLIC_URL=https://<domen>` (ariza havolalari va Telegram havolalari shu bilan yasaladi), `TELEGRAM_BOT_TOKEN`, ixtiyoriy `ANTHROPIC_API_KEY`. Keyin `make up`.
2. **Lavozim zinapoyasi** (`/career/levels`) ni **mijoz tasdiqlagandan keyin** to'ldiring: oy oxirida (31-kuni, 09:00 dan keyin) attestatsiya zinapoyadagi lavozimlar uchun avtomatik ochiladi va xodimlarga xabar ketadi. Tayyor bo'lmaguncha bo'sh qoldiring.
3. **Haftalik xavf skaneri** (dushanba 06:00) birinchi yurishda ko'p "ketish xavfi" holati ochishi mumkin. Past ball chegarasi (50) ni oldindan ko'rib chiqing yoki birinchi dushanbadan keyin natijani HR bilan tekshiring.
4. **Kadrovik sahifasi** (`/kadr`) oxirgi 60 kunda ishga olinganlarni "hujjat kutilmoqda" deb ko'rsatadi: kadrovik belgilab chiqadi.
5. **Rollar:** yangi ruxsatlar mavjud rollarga bir marta beriladi. Yangi "HR auditor" rolini kerakli xodimga biriktiring. Mijozda maxsus sozlangan rollar bo'lsa, ularga yangi ruxsatlarni (`retention.*`, `attestation.*`, `complaints.own`, `integrations.*`) qo'lda tekshiring.
6. **Tarif** kerak bo'lsa `client.yaml` ga `plan` va `license` qo'shing ([PLANS.md](PLANS.md)); yozilmasa cheklov yo'q. O'zgargach `make up`.
7. **Telegram bot** va **20:00 koordinator hisoboti** ni haqiqiy token bilan sinang (bu ikkalasi mahalliy sinovda jonli ko'rilmagan).
8. `make doctor` ✘ siz; `make backup` + `make verify-backup`; zaxira va watchdog cron ([RUNBOOK.md](RUNBOOK.md)).

## Ehtiyot bo'ling
- **Buzuvchi o'zgarish:** `client.yaml → modules` da `false` bo'lgan modul endi API darajasida ham yopiladi (`403 module_disabled`). Mijozda o'chirilgan modul bo'lsa, undan foydalanuvchi yo'qligiga ishonch hosil qiling.
- Test ma'lumot bu arxivga bazadan kirmaydi (arxiv faqat kod). Server bazasiga hech narsa ko'chirilmaydi.
- Bu papka git repozitoriysi emas: tag qo'yish va `make upgrade` uchun avval repozitoriyga qo'ying.
