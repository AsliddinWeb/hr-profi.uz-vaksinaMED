# Eski tizimdan migratsiya

Modul: `/migration` (ruxsat `migration.manage`: Ta'sischi va HR direktor). Maqsad — eski tizimdan xodimlar va davomat tarixini **xavfsiz** ko'chirish va "eski va yangi raqamlar mos"ligini isbotlash.

## Tamoyillar

- **Dry-run = haqiqiy import.** "Tekshirish" import kodining aynan o'zini bir tranzaksiyada bajaradi (bazadagi cheklovlar ham tekshiriladi) va **bekor qiladi**. Shuning uchun tekshiruvdan o'tgan narsa import qilinganda ham o'tadi.
- **Paket (batch).** Har fayl bitta paket: yuklangan fayl MinIO da saqlanadi, yaratilgan har xodim va davomat yozuvi paket raqamini (`import_batch_id`) oladi. Paketni **orqaga qaytarish** mumkin.
- **Hech narsa ustidan yozilmaydi.** Tizimda bor xodim va bor davomat kuni o'tkazib yuboriladi (hisobotda ko'rinadi), mavjud ma'lumot o'zgarmaydi.
- **Eski ID saqlanadi** (`migration_legacy_ids`): davomat tarixi xodimga shu ID (yoki tabel №, PINFL, telefon) orqali bog'lanadi; xuddi shu fayl ikkinchi marta yuklansa takror yaratilmaydi.

## Tartib

1. **Tayyorlash.** Eski tizimdan eksport (CSV yoki Excel, birinchi qator sarlavha). Xodimlar uchun ID, F.I.SH, telefon/PINFL, bo'lim, lavozim, filial, ishga olingan/bo'shatilgan sana. Davomat uchun xodim ID, sana, keldi, ketdi.
2. **Nazorat summalarini yozib oling** (eski tizimdan): jami/faol xodimlar soni, har oy uchun davomat yozuvlari soni va ishlangan soat (filial kesimida ham). `/migration/reconcile` → "Nazorat summasi" (yoki CSV: `label,metric,period,branch,expected,tolerance`).
3. **Xodimlarni import qiling:** `/migration/new` → fayl → ustunlar avtomatik moslashadi (nomlar bo'yicha; kerak bo'lsa o'zgartiring) → **Tekshirish**. Natija: nechta yaratiladi / bog'lanadi / o'tkaziladi / xato; muammoli qatorlar sabab bilan (CSV sifatida yuklab olish mumkin). Xatolarni faylda tuzating va qayta yuklang, yoki ularni o'tkazib yuborib davom eting.
   - "Tizimda yo'q bo'lim/lavozim/filiallarni yaratish" — yoqilsa, ular ham yaratiladi (dry-run da hisobi ko'rsatiladi, qaytarishda ular ham o'chadi).
   - Bo'shatilgan xodimlar (sanasi bilan) `dismissed` holatida, ish tarixi bilan yaratiladi.
   - Tizimda allaqachon bor xodim (PINFL/pasport/telefon/ism+tug'ilgan sana) yaratilmaydi, lekin eski ID si unga **bog'lanadi**.
4. **Davomatni import qiling:** tur "Davomat tarixi", xodim qaysi maydon bo'yicha topilishini tanlang (odatda eski ID). Tungi smena (ketish ertasiga) avtomatik; 24 soatdan uzun yoki kirishdan oldingi ketish — xato. Yozuvlar `import` usuli bilan, qo'lda deb belgilanib yaratiladi; kechikish faylda bo'lsa saqlanadi (eski kechikish qayta hisoblanmaydi).
5. **Solishtiring:** `/migration/reconcile` nazorat summalarini **jonli** hisoblaydi: eski, yangi, farq, "mos/mos emas" (ruxsat etilgan farq bilan). Mos kelmagan qatorni tekshiring: ko'pincha xato qatorlar yoki o'tkazib yuborilgan takror kunlar sababchi.
6. Hammasi mos bo'lgach — paketlarni qoldiring (tarixda saqlanadi). Mos bo'lmasa — **orqaga qaytarish** va qayta import.

Paket ichidagi o'z-o'zini tekshirish: davomat dry-run/importda faylga ko'ra yoziladigan soat bazaga yozilgan soat bilan solishtiriladi ("Fayl: X soat → bazada: Y soat").

## Orqaga qaytarish

Faqat shu paket yaratganlar o'chadi. **Qaytarib bo'lmaydi** (409 `batch_in_use`), agar: xodimga tizim hisobi (login) biriktirilgan bo'lsa yoki xodimlarga boshqa paketdan/qo'lda davomat yozilgan bo'lsa. Tartib: avval davomat paketini, keyin xodimlar paketini qaytaring.

## Shablonlar

Bir eski tizimdan bir necha fayl keladi (oylar bo'yicha): ustun moslashtirishini **shablon** sifatida saqlang (`/migration/templates`), keyingi fayllarda bir bosishda qo'llang.

## Cheklovlar va keyingi qadamlar

- Hozir ikki tur: xodimlar va davomat tarixi. Boshqa tarix (ta'til, jarima, oylik hisob-kitoblar) uchun nazorat summalari bilan solishtirish mumkin, lekin import yo'q; kerak bo'lsa yangi tur `app/services/migration.py` dagi `FIELDS`/`PROCESSORS` ga qo'shiladi.
- Limitlar: xodimlar 20 000 qator, davomat 200 000 qator, fayl 25 MB.
- Nazorat summasi metrikalari: xodimlar jami/faol/bo'shatilgan, davomat yozuvlari soni va soati (oy va filial bo'yicha).
- **Haqiqiy eski tizim fayli bilan sinov kutilmoqda:** ustun nomlari/sana formatlari mijozdan mijozga farq qiladi; birinchi haqiqiy fayl bilan avval alohida (staging) nusxada dry-run qiling.
