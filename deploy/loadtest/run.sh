#!/usr/bin/env bash
# Yuk testi: ALOHIDA bazada (vaksina_load) va alohida api konteynerida (cheklovsiz; WEB_CONCURRENCY=3 standart), haqiqiy ma'lumotga tegmaydi.
#   make loadtest [ARGS="--employees 2000 --users 40 --duration 45 --stages 10,30,60 --p95-limit 1.0"]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
set -a; . ./.env; set +a
EMP=2000 USERS=40; PASS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --employees) EMP="$2"; shift 2 ;;
    --users) USERS="$2"; PASS+=(--users "$2"); shift 2 ;;
    *) PASS+=("$1"); shift ;;
  esac
done
NET="$(docker compose ps -q api | head -1 | xargs docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')"
IMG="$(docker compose images api -q 2>/dev/null | head -1)"; IMG="$(docker inspect -f '{{.Config.Image}}' "$(docker compose ps -q api | head -1)")"
DB="${POSTGRES_DB}_load"
PSQL() { docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 "$@"; }
cleanup() { docker rm -f vk-load-api >/dev/null 2>&1 || true; PSQL -c "DROP DATABASE IF EXISTS \"$DB\" WITH (FORCE)" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
PSQL -c "CREATE DATABASE \"$DB\"" >/dev/null
ENVS=(-e "DATABASE_URL=postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@db:5432/$DB" -e REDIS_URL=redis://redis:6379/5 -e RATE_LIMIT_ENABLED=false -e ALLOW_SEED_LOAD=1
      -e "SECRET_KEY=$SECRET_KEY" -e "MINIO_ROOT_USER=$MINIO_ROOT_USER" -e "MINIO_ROOT_PASSWORD=$MINIO_ROOT_PASSWORD" -e CLIENT_DIR=/nonexistent -e ENV=production -e "WEB_CONCURRENCY=${WEB_CONCURRENCY:-3}")
echo "[1/4] Test API ishga tushirilmoqda (alohida baza: $DB)..."
docker run -d --name vk-load-api --network "$NET" "${ENVS[@]}" "$IMG" >/dev/null
for _ in $(seq 1 60); do docker exec vk-load-api python -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/health', timeout=2)" >/dev/null 2>&1 && break; sleep 2; done
echo "[2/4] Ma'lumot yaratilmoqda ($EMP xodim, 30 kun davomat)..."
docker exec vk-load-api python -m app.cli seed-load "$EMP" "$USERS"
echo "[3/4] Yuk berilmoqda..."
docker cp deploy/loadtest/loadtest.py vk-load-api:/tmp/loadtest.py
docker exec vk-load-api python /tmp/loadtest.py --base http://localhost:8000 "${PASS[@]}"
