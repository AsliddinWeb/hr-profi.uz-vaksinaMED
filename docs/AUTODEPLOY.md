# Avtomatik deploy: GitHub → server

`main` ga push qilinganda GitHub avval testlarni (CI) o'tkazadi. Ular yashil bo'lsa, serverga SSH orqali kirib
`deploy/scripts/upgrade.sh` ni ishga tushiradi: zaxira → yangi kod → build → migratsiya → tekshiruv.
Qo'lda buyruq yozish shart emas.

Kalit va parollar faqat GitHub'ning yopiq sozlamalarida (Secrets) saqlanadi, kodga yozilmaydi.

## Bir martalik sozlash (10 daqiqa)

### 1. Serverda deploy uchun alohida SSH kalit yarating

Server terminalida:

```bash
ssh-keygen -t ed25519 -N "" -C "github-deploy" -f ~/.ssh/github_deploy
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_deploy          # yopiq kalit — 2-qadamda GitHub'ga qo'yiladi
ssh-keyscan -t ed25519 localhost 2>/dev/null | sed "s/^localhost/$(curl -s ifconfig.me)/"   # host kaliti — 3-qadam
```

### 2. GitHub → repozitoriy → Settings → Secrets and variables → Actions → **Secrets**

| Nomi | Qiymati |
|---|---|
| `DEPLOY_KEY` | `~/.ssh/github_deploy` faylining to'liq matni (`-----BEGIN ...` dan `-----END ...` gacha) |

### 3. O'sha sahifa → **Variables** bo'limi

| Nomi | Qiymati (namuna) |
|---|---|
| `DEPLOY_HOST` | serveringiz IP manzili |
| `DEPLOY_USER` | `root` (yoki serverga kiradigan foydalanuvchi) |
| `DEPLOY_PATH` | `/opt/hr-profi` |
| `DEPLOY_URL` | `https://vaksinahr.uz` |
| `DEPLOY_KNOWN_HOSTS` | 1-qadamdagi `ssh-keyscan` natijasi (bitta qator: `IP ssh-ed25519 AAAA...`) |

### 4. Tekshirish

GitHub → **Actions** → **Deploy** → **Run workflow**. Yashil bo'lsa — tayyor: endi har bir push o'zi serverga chiqadi.

## Qo'lda yangilash (avvalgidek)

```bash
cd /opt/hr-profi && git pull && bash deploy/scripts/upgrade.sh main
```

## Muammo bo'lsa

- **Deploy "skipped"**: `DEPLOY_KEY` qo'shilmagan yoki CI qizil (Actions → CI ni oching).
- **Host key verification failed**: `DEPLOY_KNOWN_HOSTS` qiymati serverning haqiqiy kalitiga mos emas — 1-qadamdagi `ssh-keyscan` ni qayta bajaring.
- **upgrade.sh xatosi**: chiqqan xabarda zaxira nomi va orqaga qaytarish buyrug'i bor (`docs/UPGRADE.md`).
