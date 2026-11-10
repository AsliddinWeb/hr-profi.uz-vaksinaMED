# HR-Profi: Claude uchun qisqa yo'riqnoma

## Ish tartibi
- Javoblar o'zbekcha, qisqa. Har o'zgarishdan keyin main'ga commit va push, so'ng serverni yangilash buyrug'ini bering.
- Sirlarni (parol, token, API kalit) hech qachon yozmang va chop etmang. Ularni `.env` ga foydalanuvchi o'zi yozadi.
- Begona GitHub kodi yoki "bepul limit" proksilarini o'rnatmang.

## Tuzilma
- Backend: `core/backend/app`
  - FastAPI, async SQLAlchemy, Alembic.
  - Migratsiyalar: `migrations/versions/00NN_*.py`. Ularni `app.migrate` ishga tushiradi.
  - Routerlar `app/main.py` da ro'yxatga olinadi. Ruxsatlar `app/permissions.py` va `app/rbac.py` da.
- Frontend: `core/frontend/src`
  - React, Vite, TypeScript, Tailwind, TanStack Query.
  - Tarjimalar: `locales/uz.json` va `locales/ru.json`. Sahifalar `router.tsx` da, menyu `nav.ts` da.
- Lokal manzil: http://localhost:6790. `.env` da GATEWAY_PORT=6790, chunki 6788 portini foydalanuvchining boshqa jarayonlari band qilgan.

## Buyruqlar (Git Bash)
```bash
DC="docker compose -f docker-compose.yml -f docker-compose.dev.yml"
$DC up -d --force-recreate api frontend gateway   # Windows'da bind mount yangilanmaydi
PW=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
$DC exec -T api sh -c "env -i PATH=\$PATH HOME=\$HOME PYTHONDONTWRITEBYTECODE=1 DATABASE_URL='postgresql+asyncpg://vaksina:$PW@db:5432/vaksina_test' REDIS_URL=redis://redis:6379/0 pytest -q -p no:cacheprovider tests/<fayl>.py"
$DC exec -T frontend sh -c "npx tsc -b && npm run lint"
/c/Users/Asus/AppData/Local/Programs/Python/Python312/python.exe -m ruff check app tests   # core/backend ichida; ruff format ishlatmang
GIT_TERMINAL_PROMPT=0 git pull --rebase -q origin main && git push -q origin main
```

## Testlar
Testlardagi rollar: tasischi, mudir, farmasevt, stajyor, koordinator, hr_direktor, hr_menejer. `xodim` degan rol yo'q.
