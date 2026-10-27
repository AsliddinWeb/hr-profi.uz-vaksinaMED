#!/usr/bin/env bash
# Mijoz zaxirasi: PostgreSQL (pg_dump -Fc) + MinIO fayllari + manifest -> bitta arxiv (+ sha256).
#
# Ishlatish (loyiha ildizidan):  deploy/scripts/backup.sh [--out DIR] [--keep N] [--with-env] [--no-files]
#   --out DIR     arxivlar papkasi (standart: backups/)
#   --keep N      eng yangi N ta arxivni saqlaydi (standart 14)
#   --with-env    .env ni ham qo'shadi (SIRLAR! SECRET_KEY/FACE_ENCRYPTION_KEY tiklash uchun kerak). BACKUP_PASSPHRASE bilan shifrlash tavsiya etiladi
#   --no-files    faqat baza (MinIO fayllarisiz)
# .env da: BACKUP_PASSPHRASE (arxivni AES-256 bilan shifrlaydi -> .tar.gz.enc), S3_ENDPOINT/S3_BUCKET/S3_ACCESS_KEY/S3_SECRET_KEY (tashqi nusxa)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT="$ROOT/backups" KEEP=14 WITH_ENV=0 FILES=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="${2:?}"; shift 2 ;;
    --keep) KEEP="${2:?}"; shift 2 ;;
    --with-env) WITH_ENV=1; shift ;;
    --no-files) FILES=0; shift ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Noma'lum parametr: $1" >&2; exit 1 ;;
  esac
done
[[ -f .env ]] || { echo ".env topilmadi (loyiha ildizidan ishga tushiring)" >&2; exit 1; }
set -a; . ./.env; set +a
COMPOSE="docker compose"
STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="${CLIENT_NAME:-client}-$STAMP"
mkdir -p "$OUT"
WORK="$(mktemp -d "$OUT/.work.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

echo "[1/4] Baza (pg_dump)..."
$COMPOSE exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner > "$WORK/db.dump"
[[ -s "$WORK/db.dump" ]] || { echo "pg_dump bo'sh chiqdi" >&2; exit 1; }

if [[ "$FILES" == 1 ]]; then
  echo "[2/4] Fayllar (MinIO)..."
  mkdir -p "$WORK/files"
  $COMPOSE run --rm --no-deps -T -v "$WORK/files:/out" --entrypoint sh minio -c \
    "mc alias set l http://minio:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc mb --ignore-existing l/${MINIO_BUCKET:-vaksina} >/dev/null && mc mirror --quiet l/${MINIO_BUCKET:-vaksina} /out" >/dev/null
else
  echo "[2/4] Fayllar o'tkazib yuborildi (--no-files)"
fi

echo "[3/4] Manifest..."
q() { $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1" 2>/dev/null || true; }
VERSION="$($COMPOSE exec -T api python -c 'from app import __version__; print(__version__)' 2>/dev/null | tr -d '\r' || true)"
cat > "$WORK/manifest.json" <<JSON
{
  "client": "${CLIENT_NAME:-}",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "app_version": "${VERSION:-unknown}",
  "core_revision": "$(q 'select version_num from alembic_version limit 1')",
  "client_revision": "$(q 'select string_agg(version_num, $$,$$) from alembic_version_ext')",
  "database": "$POSTGRES_DB",
  "tables": "$(q "select count(*) from information_schema.tables where table_schema='public'")",
  "employees": "$(q 'select count(*) from employees')",
  "files": $( [[ "$FILES" == 1 ]] && find "$WORK/files" -type f | wc -l | tr -d ' ' || echo 0 ),
  "env_included": $( [[ "$WITH_ENV" == 1 ]] && echo true || echo false )
}
JSON
[[ "$WITH_ENV" == 1 ]] && { cp .env "$WORK/env"; chmod 600 "$WORK/env"; }

echo "[4/4] Arxiv..."
ARCHIVE="$OUT/$BASE.tar.gz"
tar -czf "$ARCHIVE" -C "$WORK" .
if [[ -n "${BACKUP_PASSPHRASE:-}" ]]; then
  openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_PASSPHRASE -in "$ARCHIVE" -out "$ARCHIVE.enc"
  rm -f "$ARCHIVE"; ARCHIVE="$ARCHIVE.enc"
elif [[ "$WITH_ENV" == 1 ]]; then
  echo "OGOHLANTIRISH: arxivda .env (sirlar) bor, lekin BACKUP_PASSPHRASE berilmagan: arxivni faqat xavfsiz joyda saqlang." >&2
fi
chmod 600 "$ARCHIVE"
( cd "$OUT" && { sha256sum "$(basename "$ARCHIVE")" 2>/dev/null || shasum -a 256 "$(basename "$ARCHIVE")"; } > "$(basename "$ARCHIVE").sha256" )

# Tashqi nusxa
if [[ -n "${S3_ENDPOINT:-}" && -n "${S3_BUCKET:-}" ]]; then
  echo "S3 ga yuklanmoqda..."
  docker run --rm -v "$OUT:/b:ro" -e H="$S3_ENDPOINT" -e K="${S3_ACCESS_KEY:-}" -e S="${S3_SECRET_KEY:-}" --entrypoint sh minio/mc -c \
    "mc alias set r \"\$H\" \"\$K\" \"\$S\" >/dev/null && mc cp /b/$(basename "$ARCHIVE") /b/$(basename "$ARCHIVE").sha256 r/$S3_BUCKET/ >/dev/null" \
    && echo "S3: yuklandi" || echo "OGOHLANTIRISH: S3 ga yuklab bo'lmadi (mahalliy nusxa saqlangan)" >&2
fi

# Eskilarini tozalash
ls -1t "$OUT"/"${CLIENT_NAME:-client}"-*.tar.gz* 2>/dev/null | grep -v '\.sha256$' | tail -n +"$((KEEP + 1))" | while read -r old; do rm -f "$old" "$old.sha256"; done

SIZE="$(du -h "$ARCHIVE" | cut -f1)"
echo "Tayyor: $ARCHIVE ($SIZE)"
