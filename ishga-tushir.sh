#!/usr/bin/env bash
# HR-Profi: bir bosishda yangilash va lokal ishga tushirish.
# Qayerdan ishga tushirilsa ham loyiha papkasini o'zi topadi.
set -e
REPO_URL="https://github.com/AsliddinWeb/hr-profi.uz-vaksinaMED.git"

# 1) Loyiha papkasini topish
find_repo() {
  local here; here="$(cd "$(dirname "$0")" && pwd)"
  for d in "$HR_PROFI_DIR" "$here" \
           "$HOME/OneDrive/Desktop/prekt/hr-profi.uz-vaksinaMED" \
           "$HOME/Desktop/prekt/hr-profi.uz-vaksinaMED" \
           "$HOME/OneDrive/Desktop/prekt/hr-profi-git"; do
    [ -n "$d" ] && [ -f "$d/docker-compose.yml" ] && { echo "$d"; return; }
  done
}
DIR="$(find_repo)"
if [ -z "$DIR" ]; then
  DIR="$HOME/OneDrive/Desktop/prekt/hr-profi.uz-vaksinaMED"
  echo "Kod topilmadi, GitHub'dan yuklanmoqda: $DIR"
  git clone -q "$REPO_URL" "$DIR"
fi
cd "$DIR"
echo "Loyiha: $DIR"

# 2) Docker ishlayaptimi? Bo'lmasa yoqib, kutish
if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop yoqilmoqda..."
  DD="$LOCALAPPDATA/Programs/DockerDesktop/Docker Desktop.exe"
  [ -f "$DD" ] || DD="/c/Program Files/Docker/Docker/Docker Desktop.exe"
  start "" "$DD" 2>/dev/null || "$DD" >/dev/null 2>&1 &
  for i in $(seq 1 90); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || { echo "Docker 3 daqiqada ochilmadi."; read -r -p "Enter..."; exit 1; }
fi

echo "1/3 Kod yangilanmoqda..."
GIT_TERMINAL_PROMPT=0 git pull --rebase --autostash -q origin main || echo "git pull o'tmadi, mavjud kod bilan davom etiladi"

if [ ! -f .env ]; then
  echo "2/3 .env yaratilmoqda (sirlar tasodifiy)..."
  cp .env.example .env
  for k in SECRET_KEY POSTGRES_PASSWORD MINIO_ROOT_PASSWORD LIVEKIT_API_SECRET; do
    sed -i "s|^$k=__generate__|$k=$(openssl rand -hex 24)|" .env
  done
  sed -i 's/^GATEWAY_PORT=.*/GATEWAY_PORT=6790/' .env
else
  echo "2/3 .env mavjud, tegilmadi"
fi

echo "3/3 Docker ishga tushirilmoqda (birinchi marta bir necha daqiqa)..."
DC="docker compose -f docker-compose.yml -f docker-compose.dev.yml"
# Kompyuter qayta yonganda API birinchi marta sekin ko'tariladi (migratsiya + reload): health kutish vaqti tugasa, kutib qayta urinamiz
if ! $DC up -d --build --remove-orphans; then
  echo "API sekin ko'tarilyapti, kutilmoqda..."
  for i in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Health.Status}}' vaksinahr-api-1 2>/dev/null)" = healthy ] && break; sleep 5; done
  $DC up -d
fi
PORT=$(grep '^GATEWAY_PORT=' .env | cut -d= -f2- | tr -d '\r')
URL="http://localhost:${PORT:-6790}"
for i in $(seq 1 30); do curl -s -o /dev/null "$URL" && break; sleep 2; done
echo "Tayyor: $URL"
[ -n "$NO_PAUSE" ] && exit 0
start "$URL" 2>/dev/null || true
read -r -p "Yopish uchun Enter..."
