# Core yangilash (mijoz serveri)

Core `git tag` bilan versiyalanadi (`vX.Y.Z`); joriy versiya `GET /api/v1/meta` → `version` va `app/__init__.py`. O'zgarishlar: [CHANGELOG.md](../CHANGELOG.md).

## Odatdagi yangilash

```bash
make upgrade TAG=v0.29.0        # = deploy/scripts/upgrade.sh v0.29.0
```

Skript tartibi: (1) **zaxira** `backups/` ga; (2) `git checkout <tag>`; (3) `client.yaml` ni yangi sxema bo'yicha tekshirish; (4) `docker compose up -d --build` (api startida core va mijoz migratsiyalari avtomatik); (5) `/api/health/ready` kutish va yangi versiyani chiqarish. Ishchi papkada commit qilinmagan o'zgarish bo'lsa to'xtaydi.

## Yangilashdan oldin (5 daqiqa)

1. `CHANGELOG.md` dan **"Buzuvchi o'zgarishlar"** bo'limini o'qing (client.yaml kalitlari, hodisa nomlari, extension API).
2. `make verify-backup FILE=<oxirgi arxiv>` — zaxira yaroqli ekaniga ishonch hosil qiling.
3. Ish vaqtidan tashqari bajaring: api qayta ishga tushganda 10–30 soniya uzilish bo'ladi.
4. Extension bor mijozda: `make validate-client` ogohlantirishlarini ko'ring; staging nusxada sinab ko'rish tavsiya etiladi.

## Muvaffaqiyatsiz bo'lsa: qaytarish

Migratsiyalar odatda orqaga qaytarilmaydi, shuning uchun qaytarish = **eski kod + zaxira**:

```bash
git checkout <eski-tag>
make restore FILE=backups/<yangilashdan-oldingi-zaxira> ARGS=--yes
```

(`upgrade.sh` xato bersa shu buyruqni zaxira nomi bilan chop etadi.)

## Qoidalar (yangilash xavfsiz bo'lishi uchun)

- Core migratsiyalari faqat **oldinga** va **orqaga mos** (eski ustun darrov o'chirilmaydi; ikki versiya davomida saqlanadi).
- Extension core jadvallariga tegmaydi va faqat hujjatlashtirilgan hodisa/endpointlarga tayanadi ([EXTENSIONS.md](EXTENSIONS.md)); shuning uchun core minor yangilanishi extension'ni buzmaydi.
- Buzuvchi o'zgarish faqat major versiyada va CHANGELOG da alohida ko'rsatiladi.
- Mijoz `client.yaml` dagi noma'lum kalitlar yangilashdan keyin xatoga aylanishi mumkin: `make validate-client` ni har yangilashda ishga tushiring.

## Yangi versiya chiqarish (ishlab chiquvchi uchun)

1. `core/backend/app/__init__.py` da `__version__`, `CHANGELOG.md` ni yangilang.
2. `make test lint` toza bo'lsin.
3. `git tag -a vX.Y.Z -m "..." && git push --tags`.
