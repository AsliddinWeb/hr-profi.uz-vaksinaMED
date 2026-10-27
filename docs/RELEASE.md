# Production chiqarish (release) tartibi

## Darvoza (hammasi bajarilmaguncha tag qo'yilmaydi)

| # | Shart | Buyruq / dalil |
|---|---|---|
| 1 | Barcha testlar yashil (backend + xavfsizlik) | `make test` |
| 2 | Frontend lint va tip tekshiruvi toza | `make lint` |
| 3 | Bog'liqlik auditi toza | `pip-audit -r core/backend/requirements.txt`, `cd core/frontend && npm audit --omit=dev` |
| 4 | Yangi migratsiyalar bo'sh va to'ldirilgan bazada o'tdi; `make test` migratsiyalarni noldan qo'llaydi | |
| 5 | Zaxira **tiklandi** (mashq) | `make verify-backup`; chorakda bir marta to'liq mashq ([BACKUP.md](BACKUP.md)) |
| 6 | Yuk testi chegarada | `make loadtest` ([LOADTEST.md](LOADTEST.md)) |
| 7 | `CHANGELOG.md` va `__version__` yangilandi; buzuvchi o'zgarishlar ajratilgan | |
| 8 | Xavfsizlik checklisti ([SECURITY.md](SECURITY.md)) ko'rib chiqildi, yangi endpoint avtomatik supurishdan o'tdi | |

## Chiqarish

```bash
git tag -a vX.Y.Z -m "..." && git push --tags
```

## Mijozda yangilash

[UPGRADE.md](UPGRADE.md): `make upgrade TAG=vX.Y.Z` (zaxira → kod → build → migratsiya → tekshiruv). Keyin `make doctor` va `make smoke`.

## Yangi mijoz bilan birinchi ishga tushirish (go-live)

1. [NEW-CLIENT.md](NEW-CLIENT.md) bo'yicha ko'tarish; `make doctor` da ✘ yo'q.
2. Migratsiya kerak bo'lsa: [MIGRATION.md](MIGRATION.md) — staging nusxada dry-run, keyin ish vaqtidan tashqari import va solishtirish.
3. Birinchi zaxira + `verify-backup`; cron (zaxira, watchdog).
4. Ta'sischi parolini almashtirish, rollar va ruxsatlarni mijoz bilan kelishish, xodimlarga kirish ma'lumotlarini berish.
5. Qo'ng'iroq sinovi (ikki xil tarmoq), Telegram bot, (ixtiyoriy) AI kaliti.
6. Mijozga topshirish: `.env` va `BACKUP_PASSPHRASE` nusxasi xavfsiz joyda; runbook ([RUNBOOK.md](RUNBOOK.md)) ko'rsatildi.
