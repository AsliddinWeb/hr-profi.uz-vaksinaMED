# Yuk testi

`make loadtest [ARGS="--employees 2000 --users 40 --duration 45 --stages 10,30,60 --p95-limit 1.0"]`

Skript (`deploy/loadtest/`) **alohida baza** (`<db>_load`) va alohida API konteynerini ko'taradi (haqiqiy ma'lumotga tegmaydi, tugagach ikkalasi o'chadi), sun'iy ma'lumot yaratadi (`ALLOW_SEED_LOAD=1` faqat shu konteynerda), so'ng haqiqiy foydalanuvchilar aralash trafigini beradi: 12% HR (xodimlar ro'yxati/kartasi, davomat tahlili hafta/oy, tabel, qidiruv, topshiriqlar, Excel hisobot) va 88% xodim (profil, bildirishnomalar, davomat, topshiriq/ticket/ehtiyoj ro'yxati, ticket yaratish), har so'rov orasida 50–400 ms "o'ylash". Chiqish kodi 1: p95 > chegara yoki xato > 1%.

## Natija (lokal, Docker Desktop, 10 yadro; yuk generatori ham shu mashinada)

Ma'lumot: 2 000 xodim, ~42 000 davomat yozuvi (30 kun), 600 topshiriq, 300 ticket, 45 foydalanuvchi. API: `WEB_CONCURRENCY=3`.

| Parallel foydalanuvchi | RPS | p50 | p95 | p99 | Xato |
|---|---|---|---|---|---|
| 10 | 98 | 4 ms | 106 ms | 604 ms | 0% |
| 30 | 156 | 30 ms | 682 ms | 823 ms | 0% |
| 60 | 238 | 82 ms | 705 ms | 963 ms | 0% |

Qayta ishga tushirishda 60 foydalanuvchi bosqichida p95 0.7–1.0 s oralig'ida tebrandi (chegara chegarasida); xato hamma yurishlarda 0%. Eng og'ir amallar: oylik davomat tahlili (p95 ~1.7 s), Excel hisobot, ticket yaratish. Bitta jarayon (`WEB_CONCURRENCY=1`) ~100 RPS da to'yingan edi; 3 jarayon bilan ~240 RPS.

## Xulosa va imkoniyat

- 60 **doimiy faol** foydalanuvchi (har biri sekundiga ~4 so'rov — haqiqiy ish ritmidan ancha tez) 0% xato bilan ushlanadi; 500 xodimli tarmoq uchun (bir vaqtda 20–40 faol) katta zaxira bor.
- Cheklovchi omil — API jarayonlari CPU si: `WEB_CONCURRENCY` ni CPU yadrolariga yaqin qiling (har jarayon ~150 MB). Keyingi qadam kerak bo'lsa: oylik tahlilni keshlash yoki hisobotni worker ga o'tkazish.
- Natijalar lokal Mac da olindi; productionga o'xshash droplet (4 vCPU / 8 GB) da `make loadtest` ni bir marta ishga tushirib, shu jadvalni yangilang.
- Faqat ilova qatlami o'lchandi (nginx cheklovlari va TLS chetda). WebSocket, LiveKit media (7881/7882) va GPS oqimi alohida (real qurilma) sinovga muhtoj.
