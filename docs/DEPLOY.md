# Serverga chiqarish (hr-profi.uz, 134.209.3.36)

Ikki yo'l bor, ikkalasi ham bir xil ishni qiladi (`deploy/scripts/upgrade.sh`):
**zaxira → kod (git) → build → migratsiya (api startida) → tekshiruv**. Xato bo'lsa zaxira nomi va qaytarish tartibi chiqadi.

| Yo'l | Qachon | Qanday |
|---|---|---|
| Avtomatik (GitHub Actions) | `main` ga har push, CI yashil bo'lgach | `.github/workflows/deploy.yml` |
| Qo'lda (kompyuterdan) | istalgan payt | `deploy/scripts/deploy.sh` |

## Bir martalik sozlash

### 1. SSH kalitlarni serverga qo'shish

Kompyuterda ikki kalit yaratilgan (`C:\Users\<siz>\.ssh\`): `hrprofi_deploy` (qo'lda deploy) va `hrprofi_actions` (GitHub).
Ularning **ochiq** (`.pub`) qismini serverga qo'shing (serverga hozirgi usulingiz bilan kirib):

```bash
cat >> ~/.ssh/authorized_keys <<'EOF'
<hrprofi_deploy.pub mazmuni>
<hrprofi_actions.pub mazmuni>
EOF
chmod 600 ~/.ssh/authorized_keys
```

Server host kaliti barmoq izi (birinchi ulanishda shu bilan solishtiring): `SHA256:LFddAZRzEGAJK3TXkrNS1k/tHgJ9nk/tRwDsI2Dq4Fg`
(serverda: `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`).

Tekshirish (kompyuterda, Git Bash): `ssh hrprofi 'hostname && docker compose version'`

### 2. Serverdagi papkani git ga ulash

Server tarball bilan o'rnatilgan bo'lsa (`/opt/vaksina` da `.git` yo'q), bir marta:

```bash
deploy/scripts/deploy.sh --init
```

Avval zaxira olinadi; `.env`, `backups/`, `clients/<mijoz>` va docker volume'lar saqlanadi.

### 3. GitHub Actions secret (avtomatik deploy uchun)

Repo **egasi** (collaborator secret qo'sha olmaydi): *Settings → Secrets and variables → Actions → New repository secret*:

- `DEPLOY_KEY` = `hrprofi_actions` (yopiq kalit, `.pub` EMAS) faylining to'liq mazmuni.
  Windows'da nusxalash: `Get-Content $HOME\.ssh\hrprofi_actions -Raw | Set-Clipboard`

Ixtiyoriy *Variables*: `DEPLOY_HOST`, `DEPLOY_USER` (standart `root`), `DEPLOY_PATH` (`/opt/vaksina`), `DEPLOY_URL` (`https://hr-profi.uz`).
`DEPLOY_KEY` bo'lmasa workflow xatosiz o'tkazib yuboriladi.

## Kundalik ish

```bash
git push origin main                 # CI yashil bo'lsa avtomatik chiqadi (Actions -> Deploy)
deploy/scripts/deploy.sh             # yoki qo'lda
deploy/scripts/deploy.sh --status    # serverdagi versiya va xizmatlar
```

Qo'lda serverda: `cd /opt/vaksina && git fetch origin main && deploy/scripts/upgrade.sh origin/main`.

## Qaytarish

`upgrade.sh` xatoda zaxira nomini chiqaradi. Kodni oldingi commitga qaytarish:
`cd /opt/vaksina && deploy/scripts/upgrade.sh <oldingi-commit>`; bazani ham qaytarish kerak bo'lsa: [BACKUP.md](BACKUP.md), [UPGRADE.md](UPGRADE.md).

## Xavfsizlik

- Kalitlar parolsiz (avtomatik ishlash uchun): kompyuterni qulflang; kalit yo'qolsa serverdagi `authorized_keys` dan uning qatorini o'chiring.
- Workflow faqat qotirilgan host kalitli serverga ulanadi va faqat `main` dagi, CI dan o'tgan commitni chiqaradi.
