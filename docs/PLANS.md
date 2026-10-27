# KOSHI tariflari

Tarif `client.yaml` dagi `plan` bilan beriladi (namuna: `clients/koshi/client.yaml`). **`plan` yozilmasa hech qanday cheklov yo'q**
(mavjud mijozlar o'zgarmaydi).

| | START ($3) | PRO ($5) | PREMIUM ($7) |
|---|---|---|---|
| Narx | foydalanuvchi / oy | foydalanuvchi / oy | foydalanuvchi / oy |
| Modullar | dashboard, org, employees, attendance, answers, discipline, tasks, reminders, checklists, internship, reports | START + face_id, calls, logistics, warehouse, payroll, mobile_tracking, recruit, recruitment, needs, pharmacy, reception, it_desk, canteen | PRO + ai, migration |
| Rollar ruxsatlarini sozlash | yo'q | bor | bor |

Tarif tarkibi `core/backend/app/plans.py` da (`PLAN_MODULES`, `FEATURES`): o'zgartirish uchun faqat shu fayl tahrirlanadi.
Imkoniyatlar jadvali **Tizim → Tarif va litsenziya** sahifasida ko'rinadi; hali ishlab chiqilmaganlari «Rejada» deb belgilanadi
(barmoq izi integratsiyasi, xarajatlar moduli, AI Agent, prognoz, avtomatik ish oqimlari, API va korporativ integratsiyalar).

## Qanday ishlaydi
- **Modullar.** Tarifga kirmagan modul menyudan yo'qoladi **va API yo'llari `403 module_disabled` qaytaradi**. `client.yaml -> modules`
  bilan tarifdagi modulni o'chirish mumkin; tarifdan tashqaridagini yoqib bo'lmaydi.
- **O'rinlar.** `license.seats`: faol foydalanuvchilar soni. Yangi foydalanuvchi, foydalanuvchini qayta yoqish va xodimga hisob
  yaratish chegaradan oshsa `409 seat_limit` bilan rad etiladi. Foydalanuvchini o'chirish o'rinni bo'shatadi.
- **Muddat.** `license.valid_until` dan keyin 14 kun faqat ogohlantirish (`grace`), undan keyin (`expired`) yangi foydalanuvchi
  qo'shib bo'lmaydi (`403 license_expired`). Kirish va mavjud foydalanuvchilar ishlashda davom etadi: tizim qulflanmaydi.
- **Ishga tushirish.** Sozlama ilova ishga tushganda o'qiladi: `client.yaml` o'zgargach `make up` (yoki api va worker ni qayta ishga tushirish) kerak.

## Eslatma
START da kiruvchi, lekin hozir alohida modul sifatida ajratilmagan imkoniyatlar (xavfsizlik va audit, smena jadvali) hamma tarifda bor.
Narxlar jadval uchun ma'lumot, hisob-kitob (billing) tizimda yuritilmaydi.
