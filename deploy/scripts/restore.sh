#!/usr/bin/env bash
# Zaxiradan tiklash yoki zaxirani TEKSHIRISH.
#
#   deploy/scripts/restore.sh <arxiv> --verify     # ishlayotgan bazaga TEGMAYDI: vaqtinchalik bazaga tiklab, tekshirib, o'chiradi
#   deploy/scripts/restore.sh <arxiv> [--yes]      # HAQIQIY tiklash: joriy baza va fayllar ALMASHTIRILADI
#
# Arxiv .tar.gz.enc bo'lsa .env da BACKUP_PASSPHRASE kerak. Tiklashdan keyin api qayta ishga tushadi va migratsiyalar
# joriy kod versiyasigacha avtomatik qo'llanadi. Yangi serverda avval `.env` ni (SECRET_KEY, FACE_ENCRYPTION_KEY bilan!) joyiga qo'ying.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
ARCHIVE="${1:-}"; shift || true
VERIFY=0 YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify) VERIFY=1; shift ;;
    --yes) YES=1; shift ;;
    *) echo "Noma'lum parametr: $1" >&2; exit 1 ;;
  esac
done
[[ -f "$ARCHIVE" ]] || { echo "Ishlatish: $0 <arxiv> [--verify|--yes]" >&2; exit 1; }
[[ -f .env ]] || { echo ".env topilmadi" >&2; exit 1; }
set -a; . ./.env; set +a
COMPOSE="docker compose"
PSQL() { $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "${1}" -v ON_ERROR_STOP=1 "${@:2}"; }

# sha256 (bo'lsa) tekshiruvi
if [[ -f "$ARCHIVE.sha256" ]]; then
  want="$(cut -d' ' -f1 "$ARCHIVE.sha256")"
  got="$( { sha256sum "$ARCHIVE" 2>/dev/null || shasum -a 256 "$ARCHIVE"; } | cut -d' ' -f1)"
  [[ "$want" == "$got" ]] || { echo "XATO: arxiv sha256 mos emas (buzilgan?)" >&2; exit 1; }
  echo "sha256: OK"
fi

mkdir -p "$ROOT/backups"
WORK="$(mktemp -d "$ROOT/backups/.restore.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
if [[ "$ARCHIVE" == *.enc ]]; then
  [[ -n "${BACKUP_PASSPHRASE:-}" ]] || { echo "Arxiv shifrlangan: .env da BACKUP_PASSPHRASE kerak" >&2; exit 1; }
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE -in "$ARCHIVE" | tar -xz -C "$WORK"
else
  tar -xzf "$ARCHIVE" -C "$WORK"
fi
[[ -s "$WORK/db.dump" && -f "$WORK/manifest.json" ]] || { echo "XATO: arxiv tuzilmasi noto'g'ri (db.dump/manifest.json yo'q)" >&2; exit 1; }
echo "--- manifest ---"; cat "$WORK/manifest.json"; echo "----------------"
mval() { sed -n "s/.*\"$1\": *\"\{0,1\}\([^\",]*\)\"\{0,1\},\{0,1\}$/\1/p" "$WORK/manifest.json" | head -1; }
M_CLIENT="$(mval client)"; M_EMP="$(mval employees)"; M_REV="$(mval core_revision)"; M_FILES="$(mval files)"

if [[ "$VERIFY" == 1 ]]; then
  TMPDB="${POSTGRES_DB}_verify"
  echo "Vaqtinchalik baza: $TMPDB (ishlayotgan baza tegilmaydi)"
  PSQL postgres -c "DROP DATABASE IF EXISTS \"$TMPDB\" WITH (FORCE)" >/dev/null
  PSQL postgres -c "CREATE DATABASE \"$TMPDB\"" >/dev/null
  trap 'PSQL postgres -c "DROP DATABASE IF EXISTS \"'"$TMPDB"'\" WITH (FORCE)" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT
  $COMPOSE exec -T db pg_restore -U "$POSTGRES_USER" -d "$TMPDB" --no-owner < "$WORK/db.dump"
  got_emp="$(PSQL "$TMPDB" -Atc 'select count(*) from employees')"
  got_rev="$(PSQL "$TMPDB" -Atc 'select version_num from alembic_version limit 1')"
  tables="$(PSQL "$TMPDB" -Atc "select count(*) from information_schema.tables where table_schema='public'")"
  got_files=0; [[ -d "$WORK/files" ]] && got_files="$(find "$WORK/files" -type f | wc -l | tr -d ' ')"
  fail=0
  [[ "$got_emp" == "$M_EMP" ]] && echo "xodimlar: $got_emp OK" || { echo "XATO: xodimlar $got_emp != $M_EMP"; fail=1; }
  [[ "$got_rev" == "$M_REV" ]] && echo "migratsiya: $got_rev OK" || { echo "XATO: migratsiya $got_rev != $M_REV"; fail=1; }
  [[ "$got_files" == "$M_FILES" ]] && echo "fayllar: $got_files OK" || { echo "XATO: fayllar $got_files != $M_FILES"; fail=1; }
  echo "jadvallar: $tables"
  [[ "$fail" == 0 ]] && echo "ZAXIRA YAROQLI" || { echo "ZAXIRA TEKSHIRUVDAN O'TMADI" >&2; exit 1; }
  exit 0
fi

if [[ "$YES" != 1 ]]; then
  echo "DIQQAT: '${POSTGRES_DB}' bazasi va MinIO fayllari ('${CLIENT_NAME:-?}') zaxira (${M_CLIENT:-?}) bilan ALMASHTIRILADI."
  read -r -p "Davom etish uchun mijoz nomini yozing (${CLIENT_NAME:-}): " ans
  [[ "$ans" == "${CLIENT_NAME:-}" ]] || { echo "Bekor qilindi"; exit 1; }
fi

echo "[1/5] Servislar to'xtatilmoqda..."
$COMPOSE up -d db minio redis >/dev/null
$COMPOSE stop api worker bot >/dev/null 2>&1 || true
echo "[2/5] Baza qayta yaratilmoqda..."
PSQL postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE)" >/dev/null
PSQL postgres -c "CREATE DATABASE \"$POSTGRES_DB\"" >/dev/null
echo "[3/5] Baza tiklanmoqda..."
$COMPOSE exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner < "$WORK/db.dump"
if [[ -d "$WORK/files" ]]; then
  echo "[4/5] Fayllar tiklanmoqda..."
  $COMPOSE run --rm --no-deps -T -v "$WORK/files:/in:ro" --entrypoint sh minio -c \
    "mc alias set l http://minio:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc mb --ignore-existing l/${MINIO_BUCKET:-vaksina} >/dev/null && mc mirror --quiet --overwrite --remove /in l/${MINIO_BUCKET:-vaksina}" >/dev/null
else
  echo "[4/5] Arxivda fayllar yo'q: MinIO tegilmadi"
fi
if [[ -f "$WORK/env" ]]; then
  echo "Arxivda .env bor; avtomatik almashtirilmaydi. Kerak bo'lsa: tar -xzOf <arxiv> ./env > .env (va chmod 600)"
fi
echo "[5/5] Servislar ishga tushirilmoqda (migratsiya avtomatik)..."
$COMPOSE up -d api worker bot >/dev/null
for _ in $(seq 1 40); do
  if curl -fsS "http://localhost:${GATEWAY_PORT:-6788}/api/health/ready" >/dev/null 2>&1; then echo "Tiklandi: tizim ishlayapti."; exit 0; fi
  sleep 3
done
echo "OGOHLANTIRISH: api 2 daqiqada tayyor bo'lmadi: docker compose logs api" >&2
exit 1
