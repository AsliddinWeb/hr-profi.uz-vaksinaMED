# client.yaml

`clients/<nom>/client.yaml` — mijoz sozlamalari. Core standartlari bilan birlashtiriladi; yozilmagan narsa standartni oladi. JSON Schema: [`clients/client.schema.json`](../clients/client.schema.json) (VS Code YAML kengaytmasi avtomatik to'ldirish va xatolarni ko'rsatadi: fayl boshidagi `# yaml-language-server: $schema=...` qatori).

Tekshirish (xatoda 1 bilan chiqadi, ogohlantirishlar faqat ko'rsatiladi):

```bash
make validate-client CLIENT=acme
```

Ilova ishga tushganda ham tekshiriladi: xatolar logga `vaksina.client` nomi bilan yoziladi va ilova **standart sozlamalar bilan ishlayveradi** (yaroqsiz qiymatlar e'tiborsiz qoldiriladi).

| Kalit | Tur | Izoh |
|---|---|---|
| `name` | matn, **majburiy** | `^[a-z][a-z0-9_-]{1,30}$`, papka nomi va `CLIENT_NAME` bilan bir xil bo'lishi kerak |
| `brand.name` | matn (1–60) | Sarlavha, login sahifasi, bildirishnomalar |
| `brand.tagline` | matn (≤120) | Yon panel ostki yozuvi |
| `brand.primary` / `brand.accent` | `#rrggbb` | Asosiy va urg'u rangi (light/dark ikkala mavzuda) |
| `brand.logo` | yo'l yoki URL | `frontend_ext/public/` ichidagi fayl yoki to'liq URL |
| `plan` | `start` / `pro` / `premium` | KOSHI tarifi: modullar tarif bo'yicha yoqiladi ([PLANS.md](PLANS.md)). Yozilmasa cheklov yo'q |
| `license.seats` | butun son ≥ 1 | Faol foydalanuvchilar soni chegarasi |
| `license.valid_until` | `YYYY-MM-DD` | Litsenziya muddati; tugagach 14 kun ogohlantirish, keyin yangi foydalanuvchi qo'shib bo'lmaydi |
| `license.holder` | matn | Litsenziya egasi (tarif sahifasida ko'rsatiladi) |
| `modules.<kalit>` | `true`/`false` | Yozilmagan modul **yoqilgan**. Ro'yxat: `core/backend/app/modules.py` (dashboard, answers, org, attendance, face_id, discipline, tasks, reminders, employees, recruitment, internship, payroll, canteen, pharmacy, recruit, checklists, needs, logistics, warehouse, mobile_tracking, reception, it_desk, calls, ai, reports). O'chirilgan modul menyudan yo'qoladi |
| `settings.timezone` | IANA nomi | Ish vaqti hisobi (davomat, hisobotlar). Standart `Asia/Tashkent` |
| `settings.map.tiles` / `.attribution` | URL shabloni `{z}/{x}/{y}` | Xarita manbai; bo'lmasa OpenStreetMap |
| `settings.<boshqa>` | istalgan | Core o'qimaydi; faqat sizning `backend_ext` kodingiz `ctx.config.settings` orqali o'qiydi (validator ogohlantiradi, xato emas) |

Noma'lum yuqori daraja kalitlar, noma'lum modul nomlari, noto'g'ri rang va vaqt mintaqasi — **xato** hisoblanadi (yozuv xatosini ushlash uchun).

Misol:

```yaml
name: acme
brand: {name: "Acme HR", primary: "#0f766e", accent: "#f97316"}
modules: {logistics: false, warehouse: false}
settings: {timezone: Asia/Tashkent, min_vacation_days: 15}   # oxirgisi extension uchun
```
