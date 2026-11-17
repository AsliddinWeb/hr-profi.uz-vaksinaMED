# Android telefonni kamera sifatida ulash

Telefon filialda kuzatuv kamerasi vazifasini bajaradi: panelda **Onlayn** ko'rinadi, oxirgi kadr ko'rinadi,
**Jonli ko'rish** bosilganda tasvir har 1,5 soniyada yangilanadi.

> Ishlash sharti: platforma **https://** manzilda ochilgan bo'lishi kerak (masalan `https://vaksinahr.uz`).
> Lokal kompyuterdagi (`localhost`) QR kod telefonda ochilmaydi.

## A. Kompyuterda (HR yoki IT xodim) — 1 daqiqa

1. `https://vaksinahr.uz` → **Filiallar tarmog'i → Kameralar**.
2. **Kamera qo'shish** → **📱 Telefon**.
3. Nomini yozing (masalan «7-filial kassa telefoni»), filial va joyini tanlang → **Davom etish**.
4. Ekranda **QR kod** chiqadi. Oynani yopmang — telefon ulanganini o'zi ko'rsatadi.

   Keyinroq ham: kameralar ro'yxatida telefonni bosing — QR kod o'sha yerda turadi.

## B. Telefonda — birinchi marta (2 daqiqa)

1. Telefon **kamera ilovasini** oching va kompyuter ekranidagi QR kodga qarating.
   Chiqqan havolani bosing (Chrome'da ochilsin).
2. Ochilgan sahifada ko'k **Ulash** tugmasini bosing.
3. «Kameraga ruxsat berilsinmi?» → **Ruxsat berish** (har safar emas, **bir marta**).
4. Kompyuterda «**Ulandi ✓**» va telefondan birinchi kadr chiqadi.

## C. Telefonda — avtomatik ishlashi uchun (1 marta sozlanadi)

1. **Bosh ekranga qo'shing:** Chrome'da o'ng yuqoridagi **⋮** → **Bosh ekranga qo'shish**
   (Добавить на главный экран) → **Qo'shish**. Bosh ekranda belgi paydo bo'ladi.
2. **Batareya cheklovini olib tashlang:** Sozlamalar → Ilovalar → **Chrome** → Batareya → **Cheklovsiz**
   (Без ограничений). Aks holda telefon Chrome'ni uxlatib qo'yishi mumkin.
3. **Zaryadga ulang** va telefonni kerakli joyga tik qo'ying (qaysi tomonni ko'rishini tekshiring).
4. **Yorqinlikni eng pastga** tushiring — ekran yoniq turadi, lekin sezilmaydi.

Shundan keyin har safar faqat **bosh ekrandagi belgini bosish** kifoya: sahifa ochiladi,
kamera **o'zi yonadi** va ekran o'chmaydi.

## D. Kundalik ishlatish

- Panelda telefonni oching → **Jonli ko'rish**: tasvir 1–2 soniyada tez rejimga o'tadi.
- To'xtatish: telefondagi **To'xtatish** tugmasi. Shundan keyin kamera keyingi safar o'zi yonmaydi —
  yana **Ulash**ni bosish kerak bo'ladi.
- Telefonni orqa kameradan old kameraga o'tkazish: **Kamerani almashtirish**.

## Muammo bo'lsa

| Belgi | Sabab va yechim |
|---|---|
| «Kameraga ruxsat berilmadi» | Chrome manzil satridagi belgi → **Ruxsatlar → Kamera → Ruxsat berish**, sahifani yangilang. |
| Panelda **Oflayn** («Signal kelmayapti») | Ekran o'chgan yoki Chrome yopilgan. Bosh ekrandagi belgini qayta bosing. C-2 (batareya) sozlamasini tekshiring. |
| QR skanerlanmaydi / sahifa ochilmaydi | Platforma `https://` manzilda ochilganini tekshiring (localhost emas). Havolani nusxalab telefonga Telegram orqali yuborish ham mumkin. |
| Tasvir qora | Kamera boshqa ilovada band (qo'ng'iroq, kamera ilovasi) — ularni yoping, sahifaga qayting: kamera o'zi qayta yonadi. |

## Muhim

- Telefon ekrani **o'chgan** bo'lsa, Android veb-sahifaga kamerani ishlatishga ruxsat bermaydi — shuning uchun ekran
  yoniq (past yorqinlikda) turishi kerak.
- Kamera yoniqligi telefonda doim ko'rinib turadi («Kamera ulangan» yozuvi). Kadrlar arxivlanmaydi — faqat oxirgisi
  15 daqiqa saqlanadi.
- Ish joyidagi videokuzatuv haqida xodimlar oldindan xabardor qilinishi kerak (ichki tartib qoidalari).
