#!/usr/bin/env bash
# GitHub Codespaces: platformani bulutda ko'taradi (kompyuterdagi Docker Desktop shart emas).
# Birinchi ochilishda: .env yaratiladi (tasodifiy parollar), manzil Codespaces domeniga moslanadi,
# konteynerlar yig'iladi va birinchi Ta'sischi hisobi yaratiladi (parol FAQAT bir marta ekranga chiqadi).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then # make init bilan bir xil: tasodifiy parollar
  cp .env.example .env
  for k in SECRET_KEY POSTGRES_PASSWORD MINIO_ROOT_PASSWORD LIVEKIT_API_SECRET; do
    sed -i "s|^$k=__generate__|$k=$(openssl rand -hex 24)|" .env
  done
  chmod 600 .env
fi

set_env() { # set_env KEY VALUE — .env dagi qatorni almashtiradi yoki qo'shadi
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}

set_env GATEWAY_BIND 0.0.0.0
set_env GATEWAY_PORT 6788
if [ -n "${CODESPACE_NAME:-}" ]; then
  set_env PUBLIC_URL "https://${CODESPACE_NAME}-6788.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
fi
# AI kalitlari GitHub > Settings > Codespaces > Secrets da saqlansa, avtomatik ulanadi (faylga qo'lda yozish shart emas)
for k in GEMINI_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY TELEGRAM_BOT_TOKEN; do
  if [ -n "${!k:-}" ]; then set_env "$k" "${!k}"; fi
done

docker compose up -d --build

echo "API ishga tushishini kutyapmiz (migratsiyalar avtomatik)..."
for _ in $(seq 1 90); do
  if curl -fsS -o /dev/null "http://localhost:6788/api/health"; then break; fi
  sleep 5
done

echo
echo "=== Birinchi Ta'sischi hisobi (parolni saqlab qo'ying, u boshqa ko'rsatilmaydi) ==="
docker compose exec -T api python -m app.cli create-admin admin "Administrator" || echo "(admin allaqachon bor)"
echo
echo "Tayyor: PORTS bo'limida 6788 portini oching (yoki brauzer o'zi ochiladi)."
