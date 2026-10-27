# Serverda eski loyihani olib tashlab, hr-profi.uz ga joylash

Hamma buyruq serverda (SSH), `root` bo'lmasangiz oldiga `sudo` qo'ying. `<...>` ichidagini o'zingiznikiga almashtiring.
**Qoida:** avval faqat KO'RING (1-qadam), keyin ZAXIRA oling (2-qadam), shundan keyingina o'chiring (3-qadam).

## 1. Serverda nima ishlayotganini tekshirish (hech narsa o'zgarmaydi)

```bash
# Server haqida: tizim, bo'sh joy, xotira, ochiq IP
cat /etc/os-release | head -2
df -h /
free -h
curl -4 -s ifconfig.me; echo

# Docker: ishlayotgan va to'xtagan konteynerlar, loyihalar, hajmlar (volume)
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker compose ls
docker volume ls

# Qaysi portlarni nima band qilgan (eski loyiha qaysi portda ekanini shu yerdan topasiz)
sudo ss -tulpn | grep LISTEN

# Nginx bormi va qaysi domenlarni qaysi portga uzatyapti
ls /etc/nginx/sites-enabled/
sudo nginx -T 2>/dev/null | grep -E "server_name|proxy_pass|listen"
```

**Eski loyiha papkasini topish** (bitta konteyner nomini `docker ps` dan oling):

```bash
docker inspect <konteyner-nomi> --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}'
```

Natija papka yo'li (masalan `/opt/old-hr`). Agar bo'sh chiqsa, konteyner `docker run` bilan ishga tushirilgan: papka yo'q, faqat nomi bor.

**Portni aniqlash:** `ss -tulpn` chiqishida eski loyiha `127.0.0.1:XXXX` yoki `0.0.0.0:XXXX` da turadi, `docker ps` ning `Ports` ustunida ham ko'rinadi (`0.0.0.0:XXXX->80/tcp`). Shu **XXXX** — "o'sha port".

**Domen serverga qaragan-qaramaganini tekshirish:**

```bash
dig +short hr-profi.uz        # chiqqan IP yuqoridagi ochiq IP bilan bir xil bo'lishi kerak
```

Agar IP boshqa bo'lsa: domen provayderida A yozuvini server IP ga o'zgartiring va tarqalishini kuting (5–30 daqiqa).

## 2. Eskisini ZAXIRALASH (bu qadamni o'tkazib yubormang)

Baza konteynerini toping (`docker ps` da `postgres` yoki `mysql` rasmi) va nusxa oling:

```bash
mkdir -p ~/old-backup && cd ~/old-backup

# Postgres bo'lsa (foydalanuvchi va baza nomini eski loyihaning .env/docker-compose.yml dan oling):
docker exec <baza-konteyneri> pg_dump -U <foydalanuvchi> <baza> > old_db.sql
# MySQL bo'lsa:
# docker exec <baza-konteyneri> mysqldump -u <foydalanuvchi> -p<parol> <baza> > old_db.sql

# Eski loyiha papkasi (kod, .env, yuklangan fayllar)
cp -r <eski-papka> ~/old-backup/project

ls -la ~/old-backup     # old_db.sql hajmi 0 emasligiga ishonch hosil qiling
```

Muhim: agar eski loyiha fayllari (rasm/hujjat) docker volume da bo'lsa, `docker volume ls` dan ularni topib nusxalang:
`docker run --rm -v <volume>:/data -v ~/old-backup:/backup alpine tar czf /backup/<volume>.tgz -C /data .`

Mumkin bo'lsa `~/old-backup` ni o'z kompyuteringizga ham oling: `scp -r user@server:~/old-backup .`

## 3. Eskisini to'xtatish va olib tashlash

**Compose loyiha bo'lsa** (papka topilgan):

```bash
cd <eski-papka>
docker compose down          # konteynerlarni to'xtatadi va o'chiradi, MA'LUMOT (volume) QOLADI
```

`down -v` ni hozir ishlatmang: u bazani ham o'chiradi. Yangi tizim ishlab, hammasi yaxshi ekaniga ishonch hosil qilgach (bir necha kundan keyin) eski hajmlarni `docker volume rm <nom>` bilan tozalaysiz.

**`docker run` bilan ishga tushirilgan bo'lsa:**

```bash
docker stop <konteyner> && docker rm <konteyner>
```

**Eski nginx sayt sozlamasini o'chirish** (eski domen o'sha portga qaragan bo'lsa):

```bash
ls /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/<eski-sayt>      # faqat havola o'chadi, asl fayl sites-available da qoladi
sudo nginx -t && sudo systemctl reload nginx
```

Tekshirish: `docker ps` da eski konteynerlar yo'q, `ss -tulpn | grep :<port>` bo'sh.

## 4. Yangi loyihani serverga qo'yish

Kompyuteringizdan (Mac) arxivni yuboring:

```bash
scp "/Users/asliddin/Desktop/Projects LIVE/vaksinaHR/dist/vaksinahr-1.1.0.tar.gz" user@<server-ip>:/tmp/
```

Serverda:

```bash
# Kerakli dasturlar: docker, make, nginx, certbot
docker compose version || curl -fsSL https://get.docker.com | sudo sh
sudo apt-get update && sudo apt-get install -y make nginx certbot python3-certbot-nginx curl

sudo mkdir -p /opt/vaksina && sudo chown "$USER":"$USER" /opt/vaksina
tar -xzf /tmp/vaksinahr-1.1.0.tar.gz -C /opt/vaksina
cd /opt/vaksina
```

## 5. Sozlash: mijoz va `.env`

```bash
deploy/scripts/new-client.sh hr-profi "HR-Profi" --domain hr-profi.uz --node-ip <server-ochiq-ip> --env
grep -E "^(CLIENT_NAME|GATEWAY_BIND|GATEWAY_PORT|PUBLIC_URL)=" .env
```

Kutilgan: `CLIENT_NAME=hr-profi`, `GATEWAY_BIND=127.0.0.1`, `PUBLIC_URL=https://hr-profi.uz`.
`.env` ichida tasodifiy sirlar o'zi yaratiladi. **`.env` nusxasini xavfsiz joyda saqlang** (parol menejeri): `SECRET_KEY` yo'qolsa Face ID ma'lumotlari tiklanmaydi.

**Port:**
- *Eng oddiysi (tavsiya):* `GATEWAY_PORT=6788` qolsin, nginx ni shu portga ulaymiz (7-qadam).
- *Eski port bilan bir xil bo'lsin desangiz:* `nano .env` va `GATEWAY_PORT=<o'sha-port>` yozing. `GATEWAY_BIND=127.0.0.1` ni o'zgartirmang: tashqariga faqat nginx (HTTPS) chiqadi.

Telegram bo'lsa `.env` ga `TELEGRAM_BOT_TOKEN=...` qo'shing (ixtiyoriy).

## 6. Ishga tushirish

```bash
make up                  # build + migratsiya + ishga tushirish (5–10 daqiqa)
make smoke               # db, redis, worker "ok" va frontend 200 bo'lishi kerak
make admin LOGIN=admin NAME="Ism Familiya"     # birinchi Ta'sischi: parol BIR MARTA chiqadi, yozib oling
docker compose ps        # hamma xizmat Up
```

Xato bo'lsa: `docker compose logs --tail=100 api` (backend), `docker compose logs --tail=100 gateway`.

## 7. Domenni ulash (nginx + HTTPS)

Avval faqat 80-port bilan oddiy sayt yarating (sertifikat hali yo'q). `<PORT>` — 5-qadamdagi gateway porti (odatda 6788):

```bash
sudo tee /etc/nginx/sites-available/hr-profi.uz >/dev/null <<'EOF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
server {
    listen 80;
    server_name hr-profi.uz www.hr-profi.uz;
    client_max_body_size 50m;
    location / {
        proxy_pass http://127.0.0.1:<PORT>;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
    }
}
EOF
sudo sed -i 's/<PORT>/6788/' /etc/nginx/sites-available/hr-profi.uz      # portni o'zingizniki bilan almashtiring
sudo ln -sf /etc/nginx/sites-available/hr-profi.uz /etc/nginx/sites-enabled/hr-profi.uz
sudo nginx -t && sudo systemctl reload nginx

curl -I http://hr-profi.uz          # 200 yoki 302 chiqishi kerak
```

Keyin sertifikat (DNS to'g'ri bo'lishi shart: 1-qadamdagi `dig`):

```bash
sudo certbot --nginx -d hr-profi.uz -d www.hr-profi.uz --redirect
```

Certbot 443 blokini va HTTP→HTTPS yo'naltirishni o'zi qo'shadi va avtomatik yangilaydi. (www kerak bo'lmasa `-d www...` ni olib tashlang.)

**Firewall** (qo'ng'iroqlar uchun 7881/7882; 6788 ochilmaydi):

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw allow 7881/tcp && sudo ufw allow 7882/udp
sudo ufw --force enable && sudo ufw status
```

Agar 7881/7882 ni eski loyiha band qilgan bo'lsa (`ss -tulpn | grep -E "7881|7882"`), `.env` da `LIVEKIT_TCP_PORT` va `LIVEKIT_UDP_PORT` ni boshqa portga o'zgartiring.

## 8. Yakuniy tekshiruv

```bash
curl -s https://hr-profi.uz/api/v1/meta | head -c 300        # "client":"hr-profi" ko'rinishi kerak
make doctor                                                    # ✘ bo'lmasligi kerak
make backup && make verify-backup FILE=backups/<oxirgi-arxiv>  # "ZAXIRA YAROQLI"
```

Brauzerda `https://hr-profi.uz` oching, 6-qadamdagi admin bilan kiring va parolni almashtiring.
`.env` dagi `PUBLIC_URL` `https://hr-profi.uz` ekanini tekshiring (o'zgartirsangiz `make up`).
Zaxira cron: [RUNBOOK.md](RUNBOOK.md), [BACKUP.md](BACKUP.md).

## Tez-tez uchraydigan muammolar

| Belgi | Sabab va yechim |
|---|---|
| `502 Bad Gateway` | nginx dagi port gateway portiga mos emas yoki loyiha ishlamayapti: `docker compose ps`, `grep GATEWAY_PORT .env`, `curl -I http://127.0.0.1:<PORT>` |
| `make up` da "port is already allocated" | Port band: `sudo ss -tulpn \| grep :<port>`: eski konteyner to'liq o'chmagan (3-qadam) |
| certbot "Challenge failed" | DNS hali serverga qaramaydi yoki 80-port yopiq: `dig +short hr-profi.uz`, `ufw status` |
| Qo'ng'iroq ishlamaydi | `LIVEKIT_NODE_IP` serverning ochiq IP si emas yoki 7881/7882 yopiq |
| Eski ma'lumot kerak bo'lib qoldi | `~/old-backup/old_db.sql` va eski papka nusxasi turibdi (2-qadam) |

## Orqaga qaytish rejasi

Yangi tizim ishlamasa: `cd /opt/vaksina && docker compose down`, nginx dagi `hr-profi.uz` saytini o'chiring, eski loyihani `cd <eski-papka> && docker compose up -d` bilan qayta ko'taring (3-qadamda `down -v` ishlatilmagani uchun ma'lumot saqlanib turadi).

## Git (keyinroq)

`.gitignore` tayyor (`.env`, zaxira, `node_modules`, `dist` kabilar kirmaydi). Birinchi marta:

```bash
cd "/Users/asliddin/Desktop/Projects LIVE/vaksinaHR"
git init && git add . && git status --short | grep -E "\.env$|node_modules|backups" ; echo "(yuqorida hech narsa chiqmasligi kerak)"
git commit -m "KOSHI/HR-Profi v1.1.0"
```

---

# Ushbu server uchun aniq reja (134.209.3.36)

Diagnostika natijasi: eski loyiha — compose project `hrprofiuz`, papka `/home/projects/hr-profi.uz`
(`docker-compose.yml` + `docker-compose.prod.yml`), portlar 127.0.0.1:8100–8104, 9100/9101.
nginx `hr-profi.uz.conf`: `hr-profi.uz` -> `127.0.0.1:8103`. DNS to'g'ri (134.209.3.36).
Server umumiy (spromaxplast, bahrombek, erp_spromax, family_market, xiu bot) — **ularga tegmang**.

## A. Xotira (eng katta xavf)
Serverda 1.9 GB RAM, ~91 MB bo'sh, swap 1.3/4 GB band. Eski hrprofiuz to'xtagach 10 ta konteyner xotirasi bo'shaydi.
Yangi stek (db, redis, minio, api, worker, bot, livekit, gateway, frontend) taxminan 1–1.5 GB oladi.
Prometheus/Grafana default o'chiq (`monitoring` profili) — yoqmang.

```bash
free -h
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | sort -k2 -h | tail -15
```
Eski stek to'xtagach `free -h` da kamida ~1 GB `available` bo'lishi kerak. Bo'lmasa swap qo'shing:
```bash
fallocate -l 2G /swapfile2 && chmod 600 /swapfile2 && mkswap /swapfile2 && swapon /swapfile2
```

## B. Eski loyihani o'rganish (hech narsa o'chmaydi)
```bash
cd /home/projects/hr-profi.uz
ls -la
grep -E "POSTGRES_(DB|USER)" .env docker-compose*.yml 2>/dev/null | sed 's/=.*PASSWORD.*/=***/'
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

## C. Zaxira (o'chirishdan OLDIN, majburiy)
```bash
mkdir -p /root/backup-hrprofi && cd /root/backup-hrprofi
# DB nomi/foydalanuvchini B bosqichdan oling (pastda — taxmin: postgres)
docker exec hrprofiuz-postgres-1 pg_dumpall -U postgres | gzip > pg_all_$(date +%F).sql.gz
cp -r /home/projects/hr-profi.uz ./project-files
for v in hr-profiuz_pgdata hr-profiuz_media hr-profiuz_miniodata hr-profiuz_redisdata; do
  docker run --rm -v $v:/d -v $PWD:/b alpine tar czf /b/$v.tgz -C /d .
done
cp /etc/nginx/sites-available/hr-profi.uz.conf .
ls -lh
```
Zaxirani o'z kompyuteringizga ham oling: `scp -r root@134.209.3.36:/root/backup-hrprofi ~/`

## D. Subdomenlar haqida qaror
admin./api./my./kiosk./files. subdomenlari eski stekka (8100–8102, 8104, 9100) ulangan. Eski stek o'chsa ular 502 beradi.
Yangi tizim bitta domenda ishlaydi (hr-profi.uz), shuning uchun ularning nginx saytlarini o'chiring (yoki
yangi gateway'ga yo'naltiring). Avval ro'yxat:
```bash
ls /etc/nginx/sites-enabled/ | grep -i hr-profi
grep -l "hr-profi.uz" /etc/nginx/sites-enabled/*
```

## E. Eski stekni to'xtatish (-v YO'Q!)
```bash
cd /home/projects/hr-profi.uz
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker ps -a | grep hrprofiuz   # bo'sh bo'lishi kerak
docker volume ls | grep hr-profiuz   # volumelar saqlanib turibdi — to'g'ri
```

## F. Yangi stekni o'rnatish
```bash
mkdir -p /opt/vaksina && cd /opt/vaksina
# kompyuterdan: scp dist/vaksinahr-1.1.0.tar.gz* root@134.209.3.36:/opt/vaksina/
sha256sum -c vaksinahr-1.1.0.tar.gz.sha256 && tar xzf vaksinahr-1.1.0.tar.gz
deploy/scripts/new-client.sh hr-profi "HR-Profi" --domain hr-profi.uz --node-ip 134.209.3.36 --env
```
Port: eski landing 8103 band edi, endi bo'sh. Eng sodda yo'l — nginx'dagi 8103 ni o'zgartirmaslik uchun `.env` da:
```bash
grep -q '^GATEWAY_PORT=' .env && sed -i 's/^GATEWAY_PORT=.*/GATEWAY_PORT=8103/' .env || echo 'GATEWAY_PORT=8103' >> .env
make up && make smoke && make admin
ss -tulpn | grep 8103   # 127.0.0.1:8103 yangi gateway
```

## G. nginx
`hr-profi.uz.conf` da `proxy_pass http://127.0.0.1:8103;` allaqachon bor — sertifikat ham mavjud, o'zgartirish shart emas.
WebSocket/katta fayl uchun `location /` ichida bo'lishi kerak:
`proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host $host; client_max_body_size 50m;`
```bash
nginx -t && systemctl reload nginx
curl -sI https://hr-profi.uz | head -3
curl -s https://hr-profi.uz/api/health
```
Eski subdomen saytlarini o'chirish (D qarori bo'yicha): `rm /etc/nginx/sites-enabled/<sayt>` -> `nginx -t && systemctl reload nginx`.

## H. LiveKit (video) portlari
```bash
ufw status | head -20
ufw allow 7881/tcp && ufw allow 7882/udp
ss -tulpn | grep -E "7881|7882"   # band bo'lmasin
```

## I. Orqaga qaytish
```bash
cd /opt/vaksina && make down
cd /home/projects/hr-profi.uz && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```
(nginx `proxy_pass` 8103 o'zgarmagani uchun eski landing o'z joyiga qaytadi.)
