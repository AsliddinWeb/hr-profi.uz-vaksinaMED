# F32–F40: yakuniy xulosa va mijozga ochiq savollar

Holat: 2026-10-27. Backend 370 test, frontend lint/tip/19 test o'tgan. Migratsiyalar 0029–0036 qo'llangan.
Manbalar: davomat hisoboti (2 PDF), Face ID xabari, "Xodim topish tizimi" taqdimoti (56 slayd), HR PROFI tijorat taklifi, PLATMA hujjatlari (Week1, Sxemalar, Itogi audita, 26-okt uchrashuv), KOSHI tariflar rasmi.

---

## 1. Yakuniy xulosa

| Faza | Nima qilindi | Asosiy sahifalar | Holat |
|---|---|---|---|
| **F32** Davomat ishonchliligi | "Davomat muammosi" so'rovi (xodim → koordinator → HR → davomat avtomatik tuzatiladi); ketishni tasdiqlash dialogi; Face ID yordam kartasi | `/attendance/issues` | Brauzerda tekshirilgan |
| **F33** Koordinator hisoboti | Koordinator × smena kesimida kelmagan/kechikkanlar, oy tarixi, uzoq kelmaganlar; sabab va chora izohi (24 soat); 20:00 avtomatik yuborish | `/attendance/coordinator-report` | Brauzerda tekshirilgan; 20:00 ishi va Telegram jonli emas |
| **F34** Zayafka → e'lon → manba | Zayafka tasdig'i (zav → HR → HRD), vakansiya avtomatik ochiladi; lavozim talablari va e'lon matni; kanallar; shaxsiy havolalar; ommaviy ariza sahifasi; manba hisoboti | `/pharmacy/needs`, `/recruit/vacancies/:id/promo`, `/apply/:kod` | Brauzerda tekshirilgan |
| **F35** Nomzod kirishi | Telegram bot (ariza), suhbat natijasi va tajriba darajasi, fon tekshiruv, AI skaner, job offer (HRD tasdig'i), rekruter paneli | `/recruit/applications/:id`, `/recruit/recruiter` | Brauzerda qisman; AI va Telegram jonli emas |
| **F36** Preboarding/onboarding | Filial paketi, 7 kunlik hisobot va fidbek, 7-kun qarori → onboarding avtomatik, oflayn darslar va qatnashuv, kadrovik | `/internship/enrollments/:id`, `/internship/classes`, `/kadr` | Brauzerda qisman |
| **F37** Attestatsiya va o'sish | Oylik attestatsiya, yig'ma baho, lavozim zinapoyasi, o'sish takliflari (HRD) | `/attestation`, `/career`, `/performance` | Brauzerda tekshirilgan |
| **F38** Ushlab qolish va nazorat | Ketish xavfi holatlari, haftalik uchrashuv, offboarding (exit-intervyu, choralar → vazifalar, dostupni yopish), nazorat paneli, HR auditor roli | `/retention`, `/offboarding`, `/control` | Brauzerda qisman |
| **F39** KOSHI tariflari | START/PRO/PREMIUM, modullar API darajasida yopiladi, o'rin va muddat chegarasi, tarif sahifasi, KOSHI namuna mijozi | `/system/plan`, `clients/koshi/` | Sahifa brauzerda; tarif rejimi faqat testda |
| **F40** Integratsiyalar | API kalitlari va tashqi API (savdo/reja), filiallarni solishtirish, shikoyat moduli | `/integrations`, `/complaints` | Solishtirish brauzerda; qolgani testda |

### Yo'lda topilgan va tuzatilgan xatolar
- F32 davomat muammolari ro'yxatida koordinator hamma filialni ko'rib qolardi (`attendance.read` ruxsati tufayli): endi faqat o'z filiallari.
- HR menejer koordinator/mudir foydalanuvchi yarata olmay qolgan edi (yangi ruxsatlar tufayli): tuzatildi.
- Suhbatdan keyin offer darajasi tanlovi yangilanmay qolgan edi (brauzerda topildi).
- Lavozim ro'yxatida bir xil nomlar ("Xodim") chalkash edi: endi "Bo'lim › Lavozim".

### Qilinmadi (qasddan yoki mijoz ma'lumotiga bog'liq)
- Kaizen takliflari, gamifikatsiya, HR byudjeti (tijorat taklifidan).
- GPP va sovuq zanjiri checklist shablonlari (GPP ro'yxati mijozda, 66 band).
- Greding (C&B) ni oylik hisobga ulash; servis va sotuv ko'rsatkichlari yig'ma bahoda.
- Offboardingda mol-mulk topshirish ro'yxati (Reviziya, AXO, Logistika, Kassa).
- Dori/FOM bilan haqiqiy ulanish (faqat ular chaqiradigan API tayyor).
- Barmoq izi, xarajatlar moduli, AI Agent, prognoz, avtomatik ish oqimlari: tarif jadvalida "Rejada".
- Davomat hisobotining PDF varianti (hozir ilova ichida va Telegram matni).
- Tijorat taklifi PDF'ida ichki qaydlar qolib ketgan (22 va 24-slaydlar): yuborishdan oldin olib tashlang.

### Ishga tushirishdan oldin (texnik ro'yxat)
1. Bazadagi test ma'lumotni tozalash: foydalanuvchilar `test_hr`, `test_coord`, `test_emp`; filial "TEST F32"; "Test Xodim", "Test Kelmagan", "Test Nomzod Ali"; TEST dasturlar va lavozimlar; test zinapoya, attestatsiya, ushlab qolish va offboarding yozuvlari.
2. `.env`: `PUBLIC_URL` (ariza havolalari uchun), `TELEGRAM_BOT_TOKEN` va bot nomi, `ANTHROPIC_API_KEY` (AI skaner uchun).
3. Lavozim zinapoyasini (`/career/levels`) faqat mijoz tasdiqlagan lavozimlarga bog'lash: oy oxirida (31-kuni) attestatsiya avtomatik ochiladi va xodimlarga xabar ketadi.
4. Haftalik xavf skaneri (dushanba) birinchi yurishda ko'p holat ochishi mumkin: past ball chegarasini (hozir 50) tekshirish.
5. Kadrovik sahifasi yaqinda ishga olinganlarni "hujjat kutilmoqda" deb ko'rsatadi: ishga tushirishdan oldin belgilab chiqish.
6. Bot, 20:00 hisobot va Telegram yuborishni haqiqiy token bilan sinash.

---

## 2. Mijozga ochiq savollar (0-faza)

Har bandda: savol, hozirgi taxmin (tizimda shunday ishlaydi), qaysi faza ta'sirlanadi. Javob kelgach taxminni o'zgartiramiz.

### A. Davomat va koordinator hisoboti (F32, F33)
1. **Filial hududi radiusi.** Taxminan 70 m deyilgan. Hozir 100 m. Aniq qiymat? *(F32)*
2. **Smena nomlari.** "2-smena" ikki xil vaqtda uchraydi: 17:00–23:59 va 18:30–24:00. Smenalarni qanday atash va qaysi vaqtlar rasmiy? *(F33)*
3. **Izoh muddati.** Koordinator kelmagan/kechikkan xodim sababini qancha vaqt ichida yozishi kerak? Hozir 24 soat. *(F33)*
4. **Jarima.** Izoh bermagan koordinatorga jarima qanday va qancha? Hozir faqat HR ga xabar boradi, jarima solinmaydi. *(F33)*
5. **Uzoq kelmaganlar.** Necha kun ketma-ket kelmasa alohida eskalatsiya (HR / ishdan bo'shatish jarayoni)? Hozir 3 kun. *(F33)*
6. **Hisobot vaqti.** 20:00 hamma smena uchun bitta vaqtmi yoki har smena uchun alohidami (masalan 2+3 va 3-smena)? *(F33)*
7. **Davomat muammosi tartibi.** Face ID/QR ishlamasa xodim kimga murojaat qiladi va tuzatishni kim tasdiqlaydi (hozir koordinator tekshiradi, HR tasdiqlaydi)? Skrinshot majburiymi? *(F32)*
8. **Hisobot ma'lumotlari.** Ro'yxatda kechikkan deb turgan, lekin smenadan oldin kelgan xodimlar (masalan 14:18 da kelgan, smena 17:00) uchun smena biriktirishi noto'g'rimi? Xodimlar smenasini kim yuritadi? *(F33)*

### B. Qidiruv, zayafka va e'lon (F34, F35)
9. **Zayafka zanjiri.** Kim yaratadi, kim tasdiqlaydi? Hozir: zaveduyushiy/koordinator → HR menejer → HRD. HRD rad etsa nima bo'ladi va muddat necha kun? *(F34)*
10. **Marketing.** Alohida rolmi? E'lonni kim joylaydi (taxmin: rekruter hh.uz/Telegram, Marketing target)? *(F34)*
11. **Nomzod soni.** Zayafkada kerakli nomzod soni oldindan belgilanadimi? Hozir "soni" bor. *(F34)*
12. **Shaxsiy havola.** Kimlar havola oladi (rekruter, trener, zaveduyushiy, koordinator)? Hozir faqat HR yaratadi. *(F34)*
13. **Suhbatni kim o'tkazadi** (rekruter yoki HR menejer/trener)? Tajribali yoki stajyor ekanini kim hal qiladi? *(F35)*
14. **Fon tekshiruv.** Kim o'tkazadi (rekruter yoki xavfsizlik xizmati) va nimalar tekshiriladi? *(F35)*
15. **Job offer.** Oylik fiks va lavozim darajasini kim belgilaydi, HRD qanday tasdiqlaydi? Offerda login/parolni Telegramga yuborishni xohlaysizmi (hozir yuborilmaydi, login xodim kartasida yaratiladi)? *(F35)*
16. **AI skaner.** AI faqat tavsiya beradimi yoki avtomatik rad etishga ham haqqi bormi (hozir faqat tavsiya)? Qaysi AI kaliti ishlatiladi? *(F35)*
17. **Telegram bot.** Nomzodlar uchun alohida bot kerakmi yoki mavjudi (xodimlar uchun) ishlatilsinmi? Bot nomi? *(F35)*

### C. Preboarding, onboarding, attestatsiya, o'sish (F36, F37)
18. **"1 kun ichida darslar va test"** nimani anglatadi: filialga borishdan oldin 1 kunlik platforma testimi (hozirgi taxmin)? *(F36)*
19. **Test chegarasi** 50% yoki 60%? Past natijada nima bo'ladi (qayta urinish, rad)? Hozir dasturdagi o'tish bali ishlaydi. *(F36)*
20. **Sovg'a.** Zo'r topshirsa nima va qaysi mezon bilan? Hozir yo'q. *(F36)*
21. **Tajribali xodim** ham 7 kunlik preboardingdan o'tadimi (taxmin: ha)? *(F36)*
22. **Onboarding dasturlari.** Har lavozim (stajyor, farmatsevt, katta farmatsevt, mudir, koordinator) uchun dars mavzulari va davomiylik (taxmin 90 kun). Qaysi lavozimlar uchun alohida dastur? *(F36)*
23. **Mentor (ustoz)** tayinlash qoidasi, mentor hisoboti va rag'bati qanday? *(F36)*
24. **Oflayn darslar.** Kun, vaqt, joy va guruh tuzish qoidasi (hozir Telegramda qo'lda yuboriladigan ro'yxatlar o'rniga)? Kelmaganlar uchun qanday choralar? *(F36)*
25. **Kadrovik.** Alohida shaxs/rolmi? Hujjat PDF yoki rasmmi, buyruq tayyorlash muddati necha kun, "buyruq tayyor" xabari kimlarga boradi? *(F36)*
26. **Attestatsiya.** Shakli (test + amaliy topshiriq?), o'tish mezoni (hozir 70 ball, test va amaliy 50/50), qaror kimniki (taxmin: HR menejer)? *(F37)*
27. **Zinapoya va o'sish.** Darajalar ro'yxati va ularning tashkiliy lavozimlarga mosligi; necha ketma-ket o'tishdan keyin o'sish taklif qilinadi (hozir 2); HRD tasdiqlaydimi? *(F37)*
28. **Greding.** Greding jadvali, fiks va bonus qoidalari (HRD va HR menejerdan). *(F37)*
29. **Yig'ma baho.** Davomat, o'qish, attestatsiya va intizom og'irliklari (hozir 30/20/30/20). Servis va sotuv ko'rsatkichlari qo'shilsinmi? *(F37)*

### D. Ushlab qolish, offboarding, nazorat (F38)
30. **Ogohlantirish muddati** 15 kun yoki 1 oy: qaysi lavozimga qaysi? *(F38)*
31. **"Vakillar"** zaveduyushiy va koordinatorlarmi? *(F38)*
32. **Haftalik uchrashuv.** Kun va vaqt, tartib, auditor xulosasi shakli? Hozir kuni belgilanmagan, 7 kun oralig'i nazorat qilinadi. *(F38)*
33. **Qaror kimniki.** Xodim qoladimi yoki ketadimi (hozir HR menejer; HRD xabardor)? *(F38)*
34. **Muddatlar.** HR suhbati (3 kun), qaror (7 kun), exit-intervyu muddati, choralar muddati, jiddiy kechikish mezoni qanday? *(F38)*
35. **HR auditor.** Kim va qaysi jarayonlarni nazorat qiladi (hozir yangi rol: ko'rish va xulosa yozish)? *(F38)*
36. **Avtomatik xavf.** Past yig'ma ball (hozir 50) ketish xavfi deb hisoblanishi to'g'rimi? Birinchi yurishda ko'p holat chiqishi mumkin. *(F38)*
37. **Offboarding.** Mol-mulk topshirish ro'yxati: Reviziya (tovar va kassa), AXO (inventar), Logistika, Kassa. Har biri uchun kim va qanday? *(F38)*
38. **Ketish sabablari ro'yxati** (maosh, rahbar, ish og'irligi, jamoa, o'sish, shaxsiy, boshqa taklif) va xavf turlari (kamomad, dostup, xodim yetishmasligi, boshqalarning ketishi, raqobatchi): to'g'rimi, qo'shiladigan bormi? *(F38)*

### E. Tarif va litsenziya (F39)
39. **Savdo modeli.** Tijorat taklifida bir martalik 18–25 mln so'm, KOSHI da oylik $3/5/7 foydalanuvchi. Qaysi mijozga qaysi? Billing tizimda yuritilsinmi? *(F39)*
40. **Tarif tarkibi.** Qaysi modul qaysi tarifga kiradi (taklif: `docs/PLANS.md`): apteka, resepshin, AyTi, Abet kabi vertikal modullarni PRO ga qo'ydik. Kelishamizmi? *(F39)*
41. **Litsenziya.** Muddat tugagach 14 kun imtiyoz, keyin yangi foydalanuvchi qo'shilmaydi (tizim qulflanmaydi). Shu to'g'rimi? *(F39)*
42. **Rejadagi imkoniyatlar** (barmoq izi: qaysi qurilma; xarajatlar moduli; AI Agent; prognoz; ish oqimlari): qaysi biri birinchi? *(F39)*

### F. Ma'lumotlar va integratsiyalar (F34–F40)
43. **Filiallar soni.** Manbaga qarab 129 / 130 / 137 / 138 / 141 / 142 / 149 / 150. Qaysi ro'yxat asosiy? Ochilish sanalari bilan to'liq ro'yxatni va yopilgan filiallarni yuborishingiz mumkinmi? *(F40)*
44. **Koordinatorlar soni** manbaga qarab 5, 13 yoki 14. Har koordinatorga biriktirilgan filiallar ro'yxati kerak. *(F33, F40)*
45. **Dori va FOM.** Savdo va reja ma'lumotini API orqali yuborish mumkinmi (kunlik, filial bo'yicha)? Kim bilan kelishamiz (Dori dasturchisi, IT boshlig'i)? Yuboriladigan maydonlar: filial raqami, sana, savdo, reja, cheklar soni. *(F40)*
46. **VaksinaHR muallifi** (PLATMA ochiq savoli): platforma kim tomonidan yozilgan va platformadan oldin xodimlar qanday o'qitilgan? *(PLATMA)*
47. **Shikoyatlar.** Anonim shikoyatni HR ko'rmasligi to'g'rimi? Kim ko'rib chiqadi (HR menejer; qaysi muddatda javob)? Telegramdagi eski murojaatlar ko'chirilsinmi? *(F40)*
48. **Dorixona checklistlari.** Farmatsevt kunlik chek-listi va sovuq zanjiri jurnali (6 jurnaldan 5 tasi elektron yuritilishi mumkin) hamda GPP tayyorgarlik ro'yxati (66 band): fayllarini yuboring, shablon sifatida qo'shamiz. *(keyingi faza)*
49. **Kaizen, gamifikatsiya, HR byudjeti.** Keraklimi va qaysi tartibda? *(keyingi faza)*

### G. Huquqiy
50. **Dasturiy mahsulotni ro'yxatdan o'tkazish.** Huquq egasi kim (siz yoki mijoz)? Dastur va bazani alohida ro'yxatdan o'tkazish tavsiya etilgan; yurist modda va qaror raqamlarini tekshirsin. Biz tayyorlaymiz: kod fragmentlari PDF (≤10 MB) va 700 belgigacha referat.

---

## 3. Javoblar kelgach qiladigan ishlar (qisqa)
- Taxmin qiymatlari (muddat, chegara, og'irlik) sozlamalarda: `/career/settings` va API orqali o'zgaradi, kod o'zgartirish kerak emas.
- Tuzilmaviy javoblar (zanjir kimlardan o'tishi, ruxsatlar, rollar, kadrovik, auditor) kodga kichik o'zgartirish bo'ladi.
- Dori/FOM formati kelishilgach: kalit yaratiladi, kunlik yuborish sinaladi, savdo hisobotidagi "xavf" qoidasi (reja < 90% va xodim yetishmaydi) mijoz bilan sozlanadi.
