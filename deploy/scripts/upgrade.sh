#!/usr/bin/env bash
# Core yangi versiyasiga o'tish: zaxira -> kodni yangilash -> build -> migratsiya -> tekshiruv.
#   deploy/scripts/upgrade.sh <git-tag-yoki-branch>
# Muvaffaqiyatsiz bo'lsa: zaxira nomi va qaytarish buyrug'i chiqariladi (docs/UPGRADE.md).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TARGET="${1:-}"
[[ -n "$TARGET" ]] || { echo "Ishlatish: $0 <tag|branch>" >&2; exit 1; }
[[ -d .git ]] || { echo "Bu papka git repozitoriysi emas" >&2; exit 1; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo "Ishchi papkada o'zgarmagan (commit qilinmagan) fayllar bor: avval ularni saqlang" >&2; exit 1; }
set -a; . ./.env; set +a

PREV="$(git rev-parse --short HEAD)"
PREV_VER="$(docker compose exec -T api python -c 'from app import __version__; print(__version__)' 2>/dev/null | tr -d '\r' || echo '?')"
echo "Hozirgi: $PREV (v$PREV_VER) -> $TARGET"

echo "[1/5] Zaxira..."
deploy/scripts/backup.sh --keep 30 | tee /tmp/vaksina-upgrade-backup.log
BACKUP="$(sed -n 's/^Tayyor: \(.*\) (.*)$/\1/p' /tmp/vaksina-upgrade-backup.log | tail -1)"
echo "[2/5] Kod yangilanmoqda..."
git fetch --tags --quiet
git checkout --quiet "$TARGET"
NEW="$(git rev-parse --short HEAD)"

echo "[3/5] Client.yaml tekshiruvi..."
docker compose build --quiet api
docker compose run --rm --no-deps api python -m app.cli validate-client "/clients/${CLIENT_NAME}" || { echo "client.yaml yangi versiyaga mos emas" >&2; }

echo "[4/5] Build va ishga tushirish (migratsiyalar api startida bajariladi)..."
docker compose up -d --build

echo "[5/5] Tekshiruv..."
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${GATEWAY_PORT:-6788}/api/health/ready" >/dev/null 2>&1; then
    NEW_VER="$(docker compose exec -T api python -c 'from app import __version__; print(__version__)' | tr -d '\r')"
    echo "Tayyor: $PREV -> $NEW (v$NEW_VER). Zaxira: ${BACKUP:-?}"
    exit 0
  fi
  sleep 3
done
cat >&2 <<MSG
XATO: yangi versiya 3 daqiqada tayyor bo'lmadi. Loglar: docker compose logs api
Qaytarish:
  git checkout $PREV
  deploy/scripts/restore.sh ${BACKUP:-<zaxira>} --yes
MSG
exit 1
