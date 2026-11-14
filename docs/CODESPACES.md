# HR-Profi'ni GitHub Codespaces'da ishlatish

Kompyuterdagi Docker Desktop shart emas: platforma GitHub bulutida ishlaydi, brauzer orqali ochiladi.

## Birinchi marta (5–10 daqiqa)

1. GitHub'da repozitoriyni oching → yashil **Code** tugmasi → **Codespaces** → **Create codespace on main**.
2. Ochilgan oynaning pastidagi terminalda o'rnatish o'zi boshlanadi (`.devcontainer/setup.sh`):
   konteynerlar yig'iladi, baza yaratiladi, oxirida **admin** login va **bir martalik parol** chiqadi — saqlab qo'ying.
3. **PORTS** bo'limida `6788` (HR-Profi) qatoridagi globus belgisini bosing — platforma brauzerda ochiladi.

## Keyingi safar

GitHub → **Code → Codespaces** → mavjud codespace'ni bosing. Platforma o'zi qayta ko'tariladi (`docker compose up -d`).

## AI kaliti (Gemini/Claude)

Kalitni faylga yozmang: GitHub → **Settings → Codespaces → Secrets** → `GEMINI_API_KEY` qo'shing va shu repozitoriyga ruxsat bering.
Yangi codespace yaratilganda kalit avtomatik ulanadi.

## Bepul limit

Shaxsiy hisobda oyiga 120 yadro-soat bepul (2 yadroli mashinada ~60 soat). Ishlatilmasa codespace 30 daqiqada o'zi uxlaydi —
soat sarflanmaydi. Ishni tugatgach GitHub → Codespaces → **Stop codespace** bosish mumkin.

## Namuna ma'lumotlar (ixtiyoriy)

Terminalda (barcha ish ma'lumotini o'chirib, namunaviy ma'lumot bilan to'ldiradi):

```bash
docker compose exec -e ALLOW_DEMO_SEED=1 api python -m app.cli seed-demo-all
```
