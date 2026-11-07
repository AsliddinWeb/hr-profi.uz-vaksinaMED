#!/usr/bin/env bash
# Serverga chiqarish (kompyuterdan, Git Bash yoki Linux/Mac terminalida):
#   deploy/scripts/deploy.sh            # main ni serverga chiqaradi: zaxira -> pull -> build -> migratsiya -> tekshiruv
#   deploy/scripts/deploy.sh --init     # BIR MARTA: tarball bilan o'rnatilgan /opt/vaksina ni git ga ulaydi
#   deploy/scripts/deploy.sh --status   # serverdagi versiya va xizmatlar holati
#
# Sozlash (ixtiyoriy, muhit o'zgaruvchilari):
#   DEPLOY_SSH=hrprofi                  # ~/.ssh/config dagi Host (standart: hrprofi)
#   DEPLOY_PATH=/opt/vaksina            # serverdagi loyiha papkasi
#   DEPLOY_URL=https://hr-profi.uz      # tashqi tekshiruv manzili
#   DEPLOY_BRANCH=main
set -euo pipefail

SSH_HOST="${DEPLOY_SSH:-hrprofi}"
REMOTE_PATH="${DEPLOY_PATH:-/opt/vaksina}"
PUBLIC_URL="${DEPLOY_URL:-https://hr-profi.uz}"
BRANCH="${DEPLOY_BRANCH:-main}"
REPO_URL="$(git config --get remote.origin.url 2>/dev/null || echo https://github.com/AsliddinWeb/hr-profi.uz-vaksinaMED.git)"
MODE="${1:-deploy}"

remote() { ssh -o BatchMode=yes "$SSH_HOST" "$@"; }

echo "== Server: $SSH_HOST:$REMOTE_PATH ($BRANCH)"
remote true || { echo "SSH ulanmadi. Kalit serverga qo'shilganini tekshiring: docs/DEPLOY.md" >&2; exit 1; }

case "$MODE" in
  --status)
    remote "cd '$REMOTE_PATH' && (git log -1 --format='%h %ci %s' 2>/dev/null || echo 'git ulanmagan') && docker compose ps --format 'table {{.Service}}\t{{.Status}}'"
    curl -fsS "$PUBLIC_URL/api/health/ready" && echo
    exit 0
    ;;
  --init)
    # .env, backups/, clients/<mijoz> va docker volume'lar saqlanadi; kuzatiladigan fayllar repodagi bilan almashtiriladi
    remote "set -e; cd '$REMOTE_PATH'
      if [ -d .git ]; then echo 'Allaqachon git repozitoriysi'; git remote -v; exit 0; fi
      command -v git >/dev/null || (apt-get update -qq && apt-get install -y -qq git)
      make backup
      git init -q -b '$BRANCH'
      git remote add origin '$REPO_URL'
      git fetch -q origin '$BRANCH'
      git checkout -f -B '$BRANCH' 'origin/$BRANCH'
      git status --short | head -20
      echo 'Git ulandi:'; git log -1 --format='%h %s'"
    echo "Endi: deploy/scripts/deploy.sh"
    exit 0
    ;;
  deploy) ;;
  *) echo "Noma'lum rejim: $MODE (--init | --status)" >&2; exit 1 ;;
esac

# Lokal tekshiruv: chiqarilayotgan commit GitHub da bo'lishi kerak (server o'sha yerdan oladi)
if git rev-parse --git-dir >/dev/null 2>&1; then
  git fetch -q origin "$BRANCH" || true
  if [ -n "$(git log "origin/$BRANCH..HEAD" --oneline 2>/dev/null)" ]; then
    echo "OGOHLANTIRISH: push qilinmagan commitlar bor, ular serverga tushmaydi:" >&2
    git log "origin/$BRANCH..HEAD" --oneline >&2
  fi
  echo "Chiqariladi: $(git log -1 --format='%h %s' "origin/$BRANCH")"
fi

remote "set -e; cd '$REMOTE_PATH'
  [ -d .git ] || { echo 'Server hali git ga ulanmagan: avval deploy/scripts/deploy.sh --init' >&2; exit 1; }
  git fetch -q origin '$BRANCH'
  deploy/scripts/upgrade.sh 'origin/$BRANCH'
  docker image prune -f >/dev/null"

echo "== Tashqi tekshiruv: $PUBLIC_URL"
for _ in $(seq 1 20); do
  if curl -fsS "$PUBLIC_URL/api/health/ready"; then echo; echo "Tayyor."; exit 0; fi
  sleep 3
done
echo "Tashqi tekshiruv o'tmadi: serverda 'docker compose logs --tail=100 api gateway' ni ko'ring" >&2
exit 1
