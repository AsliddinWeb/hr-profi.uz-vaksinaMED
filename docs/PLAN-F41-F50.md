# F41–F50: mijozning yangi talablari bo'yicha rejа (2026-10-28)

Manba: mijozning 9 ta xabari, 9 ta skrinshot (11–77.jpg, logolar, Abet) va `javob-holat-…pdf` (401 ta so'rov, 201 bet).
Hozirgi holat: F0–F40 tayyor (v1.1.0). Quyida har bir talab uchun: mijoz nima dedi → tizimda hozir nima bor → nima qilinadi.

## Talablar va hozirgi holat

| # | Mijoz talabi | Hozir | Xulosa |
|---|---|---|---|
| 1 | «Bo'limlar va lavozimlar» va «Filiallar» alohida menyu emas, **Tashkiliy tuzilma ichiga** (bosilganda ochiladigan) joylansin. **Rotatsiya yo'q**: filialdan filialga o'tkazish qo'shilsin | `nav.ts` da 3 ta alohida punkt (`org`, `departments`, `branches`). Faqat doimiy `transfer` bor (bulk ham), vaqtinchalik rotatsiya yo'q | F41 |
| 2 | **Javob olish holati** hisoboti PDF dagidek ko'rinishda (kartochka: filial, smena, koordinator, izoh, tarix) | `/answers` bor (kalendar, inbox). Holat sahifasi (KPI, oy kalendari, kim necha marta, qidiruv, filtr) va **Excel/PDF eksport yo'q**. Mijoz PDF si 44 MB/201 bet: sahifalar matnsiz (rasm) — bizniki matnli bo'lishi kerak | F42 |
| 3 | **Botda**: jami filial soni, pastida qaysi filialdan qaysi xodim necha kun oldin javob olgani; har javob uchun **elektron bildirgi** | Bot faqat bildirishnoma/nomzod oqimi. Javob hisoboti va bildirgi yo'q (`letters_pdf` + `/verify` asosi bor) | F43 |
| 4 | **Javob olish tartibi** (koordinator → HR) ko'rinishi; **har bo'lim va har lavozim uchun chek-list**, bo'lim kartochkasida va xodim panelida | Chek-listlar faqat filial tekshiruvi (`checklists`). Bo'lim/lavozim chek-listi va xodimning kunlik chek-listi yo'q | F44 |
| 5 | HR bo'limi ichida **kompaniya hujjatlari kutubxonasi** (missiya, maqsad, strategiya, qadriyat, nizom, ichki tartib, lavozim majburiyatlari, recruiting/pre/on/offboarding, baholash, C&B, Kaizen, KPI, motivatsiya, madaniyat, gamifikatsiya) va **xodimning elektron hujjatlari** (tushuntirish xati, ariza, buyruq, jarima) | Tushuntirish xati va jarima bor. **Ariza (xodim arizasi) va buyruq (HR buyrug'i) yo'q**, kutubxona yo'q | F45 |
| 6–7 | **Topshiriq berish tartibi**ni tuzatish (66/77.jpg), olingan hisobot va bildirishnomalar dizaynini ko'rib chiqish | Topshiriq: forma alohida sahifada (`/tasks/new`), chat/fayl/tarix bor. Yo'q: bir nechta mas'ulga alohida topshiriq, bo'lim/filial/guruh bo'yicha berish (skrinshotdagi «Ofis/Dorixona»), holat zanjiri ko'rinishi. Bildirishnoma markazi sodda | F46 |
| 8 | Logotip: **HR PROFI** (logo1 – och fon, logo2 – to'q fon) | Hozirgi logo `public/logo*.png`; `client.yaml` brend | F47 (kichik) |
| 9 | **Rekruting platformasi TZ** (9 modul, 3 bosqich) | F34–F36 da: zayavka→e'lon→manba, Telegram nomzod, suhbat, AI skaner, offer, onboarding. TZ ning ko'p qismi yo'q (pastda) | F48–F50 |

Eslatma: Abet skrinshoti (9.jpg) uchun matn yo'q. Ko'rinib turgani: baholash oynasi 12:30–15:00, menyu kirillcha. Savol sifatida ro'yxatga kiritilgan.

## Fazalar

### F41. Tashkiliy tuzilma yagona bo'lim + rotatsiya (kichik–o'rta) — TAYYOR 2026-10-28
- Menyu: `Tashkiliy tuzilma` bitta punkt; ichida bosilganda ochiladigan 3 bo'lim: Daraxt, Bo'limlar va lavozimlar, Filiallar (eski URL lar saqlanadi, redirect).
- **Rotatsiya**: xodimni filialdan filialga vaqtincha (sana dan–gacha, sabab) yoki doimiy o'tkazish; HR tasdiqlaydi; muddat tugasa avtomatik qaytadi; davomat/grafik/geofence o'sha davrda yangi filialga bog'lanadi; tarix xodim kartochkasida; bildirishnoma (xodim, ikki filial mudiri, koordinator).
- Qabul mezoni: rotatsiyadagi xodim yangi filialda Face ID/QR bilan belgilanadi va eski filial hisobotida «rotatsiyada» deb ko'rinadi.

### F42. «Javob olish holati» hisoboti (o'rta) — TAYYOR 2026-10-28
- Sahifa: KPI (jami, koordinatorda, HR da, tasdiqlangan, rad, bekor), oy kalendari (kunlik soni), «shu oyda kim necha marta» ro'yxati, qidiruv, holat chiplari.
- Excel va **matnli PDF** (kartochka: filial, smena, koordinator, izoh, tarix; sahifalash, filtr bo'yicha, oy/filial/koordinator).
- Mijoz PDF idagi 8 soatlik «koordinator javob bermadi → HR ga o'tdi» qoidasi hisobotda ko'rinsin.

### F43. Bot: javob hisoboti va elektron bildirgi (o'rta) — TAYYOR 2026-10-28
- Bot buyrug'i (HR/koordinator/mudir): jami filial soni → filial bo'yicha ro'yxat: xodim, necha kun oldin javob olgan, hozirgi holat.
- Tasdiqlangan har javobga **elektron bildirgi** (PDF, raqam, QR, `/verify` orqali tekshiriladi); xodimga botda yuboriladi.
- Bog'liq: F42 ma'lumotlari.

### F44. Bo'lim va lavozim chek-listlari (o'rta) — TAYYOR 2026-10-28
- Chek-list shabloni bo'limga yoki lavozimga biriktiriladi (kunlik/haftalik, punktlar: ha/yo'q, ball, foto).
- Bo'lim va lavozim kartochkasida ko'rinadi; xodimning panelida «Mening chek-listim»; bajarilish nazorati (koordinator/HR), kechikish bildirishnomasi.
- «Javob olish tartibi» qadamlari so'rov formasida qoida sifatida ko'rsatiladi.

### F45. HR hujjatlar kutubxonasi va xodim elektron hujjatlari (katta) — TAYYOR 2026-10-29
- **Kutubxona**: kategoriyalar (strategiya, siyosat va nizomlar, jarayonlar, tizimlar, madaniyat), versiyalar, rol/bo'lim bo'yicha ko'rinish, fayl yoki matn, «tanishdim» tasdig'i (kim, qachon).
- Mijoz ro'yxatidagi ~25 ta hujjat uchun bo'sh shablon-kartochkalar tayyor yaratiladi (mazmunini mijoz to'ldiradi).
- **Ariza** (ta'til, ishdan bo'shash, ko'chirish) va **buyruq** (ishga qabul, ko'chirish, ta'til, bo'shatish) — raqamlash, PDF, QR, tasdiq zanjiri; xodim kartochkasida bitta «Elektron hujjatlar» tabida tushuntirish xati, ariza, buyruq, jarima birga.

### F46. Topshiriqlar: berish tartibi va bildirishnoma dizayni (o'rta) — TAYYOR 2026-10-29
- Berish: bir nechta mas'ul (har biriga alohida topshiriq), bo'lim/filial/ish guruhi bo'yicha ommaviy berish, holat zanjiri (Yangi → Qabul → Jarayonda → Tekshiruvda → Bajarildi), qabul tasdig'i. Forma alohida sahifada qoladi (modal emas).
- Bildirishnoma markazi: guruhlash, o'qilmagan/o'qilgan, chuqur havola, foydalanuvchi sozlamasi; hisobot (Excel/PDF) dizayni F42 bilan bir uslubda.
- Avval mijozdan aniqlashtirish kerak (savollar ro'yxati, 3-band).

### F47. HR PROFI brendi (kichik)
- Logo (och/to'q fon varianti), favicon, PWA ikonlari, kirish sahifasi, PDF sarlavhalari, Telegram bot, `client.yaml` ga `logo_dark`.
- Mijoz yuborgan rasm 330×130 px past sifatli: vektor (SVG/AI) yoki 1000+ px kerak.

### F48. Rekruting 1: MVP yadrosi (katta) — TAYYOR 2026-10-29
TZ 4.1–4.5, 8.1–8.2 bo'yicha yetishmaydigani:
- **Lavozim kartochkasi** (kompetensiya: vazifa, hard/soft skill, til, istisno mezonlari, versiyalar) va zayavkada avtoto'ldirish; **zayavka SLA** (14 kun) va muddat ogohlantirishi.
- E'lon: kanal bo'yicha joylash jurnali, UTM havolalar, zayavka yopilganda e'lonlarni «Yopilgan» qilish eslatmasi.
- Nomzod: **anketa + rezyume/obyektivka yuklash**, AI o'qishi, qo'ng'iroq ma'lumoti bilan **birlashgan profil**, nomzod tasdig'i; telefon raqami **egalik tarixi** (raqam boshqa shaxsga o'tsa yangi kartochka); JSHSHIR bo'yicha dublikat.
- **Taklif**: moslik bali chegarasida avtomatik yuborish (oylik, grafik, manzil, xarita), bo'sh vaqt tanlash, 1 kun va 2 soat oldin eslatma, «Kelaman/Kela olmayman», video havola.
- Rekruter kunlik chek-listi va zayavka voronkasi (har «yo'q» uchun majburiy sabab).

### F49. Rekruting 2: intervyu, test, fon tekshiruvi, offer (katta) — TAYYOR 2026-10-29
TZ 4.6–4.8: kompetensiya bo'yicha 1–5 baho kartochkasi; test banki (IQ, mantiq, lavozim) havola orqali, vaqt cheklovi, o'tish bali; nomzod roziligi bilan fon tekshiruvi (bandlar, natija, izoh); AI yakuniy xulosa loyihasi (jinsi/yoshi/millati/dini hisobga olinmaydi); offer tasdig'i va nomzodga havola, rad etish sababi; elektron imzo (2-bosqich uchun interfeys).

### F50. Rekruting 3: integratsiyalar va KPI (katta, tashqi hisoblarga bog'liq)
IP-telefoniya (OnlinePBX/Zadarma/Sipuni: yozuv, kiruvchi qo'ng'iroqda kartochka ochish, AI matnga aylantirish), SMS (Eskiz/Play Mobile), hh.uz/olx.uz javoblari, Google Calendar/Meet/Zoom; KPI hisobotlari (yopilish muddati, kanal samaradorligi, narx), rad etish sabablari AI tahlili, intervyu audio/video AI tahlili, 2FA, ochiq API kengaytmasi.

## Tartib va bog'liqlik

| Tartib | Faza | Hajm | Eslatma |
|---|---|---|---|
| 1 | F47 brend | S | rasm sifati kerak; tezda ko'rinadi |
| 2 | F41 tuzilma + rotatsiya | M | |
| 3 | F42 javob holati hisoboti | M | F43 ning asosi |
| 4 | F43 bot + bildirgi | M | F42 dan keyin |
| 5 | F44 chek-listlar | M | |
| 6 | F45 hujjatlar | L | mazmunni mijoz beradi |
| 7 | F46 topshiriq/bildirishnoma | M | aniqlashtirish kerak |
| 8–10 | F48 → F49 → F50 | L | TZ 3 bosqichiga mos |

S ≈ 0.5–1 kun, M ≈ 2–3 kun, L ≈ 4–8 kun (test va brauzerda tekshiruv bilan).

## Muhim farq: SaaS (ko'p kompaniyali) talabi
Rekruting TZ si **ko'p kompaniyali SaaS** (har mijoz alohida ma'lumot) deb yozilgan. Bizning arxitektura: **har mijozga alohida o'rnatish** (alohida baza, `clients/<nom>`). Bu TZ talabini bajaradi (ma'lumot to'liq ajratilgan), lekin bitta umumiy platforma ichida «super admin → kompaniyalarni ulash» yo'q. Qaror kerak: hozirgi modelni saqlaymizmi yoki F50 dan keyin alohida katta faza sifatida SaaS qatlamini qo'shamizmi.

## Mijozga ochiq savollar
1. «Rotatsiya»: faqat vaqtinchalik (sana dan–gacha) yoki doimiy ko'chirish ham? Kim tasdiqlaydi (HR / ikki filial mudiri)?
2. 4-xabar: «javob olish tartibi» ostidagi chek-list — javob olish qoidalarimi yoki bo'lim/lavozim vazifalari ro'yxatimi? Chek-listni kim to'ldiradi va kim tekshiradi?
3. 6–7-xabar («topshiriqni to'g'rilash»): aynan nimasi noto'g'ri — berish ketma-ketligimi, ko'rinishimi yoki bildirishnomalarmi? Skrinshotdagi (modal) variantni qoldirish kerakmi yoki alohida sahifa?
4. Bildirgi (3-xabar): qog'oz bildirgi shaklimi? Shablon/namuna va imzo (koordinator, HR) tartibi kerak.
5. Hujjatlar kutubxonasi: mazmunni kim yozadi? Qaysilarini xodim «tanishdim» deb tasdiqlashi shart?
6. Buyruq va ariza: raqamlash formati va namunaviy shakllar (O'zbekiston kadr hujjatlari).
7. Logo: vektor yoki katta o'lchamli fayl; ranglar (to'q ko'k) brend palitrasi sifatida qabul qilinadimi?
8. Abet (9.jpg): nima o'zgarishi kerak (kirillcha menyu, baholash vaqti)?
9. Rekruting: IP-telefoniya (qaysi PBX), SMS shlyuz akkaunti, hh.uz/olx.uz API kirishi, AI (LLM/nutqni matnga) uchun kalit va byudjet; SaaS modeli kerakmi?
10. Mijoz PDF si 201 bet: oylik hisobot odatda qancha so'rovni qamrashi kerak (filtrsiz hammasi yoki filial/koordinator bo'yicha)?
