#!/usr/bin/env bash
# Oddiy kuzatuvchi (cron, har 5 daqiqa): tizim sog'ligi, disk, zaxira yoshi, sertifikat. Muammo bo'lsa Telegramga BIR marta xabar, tuzalsa "tiklandi".
#   */5 * * * * cd /opt/vaksina && deploy/scripts/watchdog.sh
# .env: TELEGRAM_BOT_TOKEN va ALERT_TELEGRAM_CHAT_ID (guruh yoki shaxsiy chat ID). Ular bo'lmasa faqat stdout/log.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }
TOKEN="$(get TELEGRAM_BOT_TOKEN)"; CHAT="$(get ALERT_TELEGRAM_CHAT_ID)"; CLIENT="$(get CLIENT_NAME)"; PORT="$(get GATEWAY_PORT)"; PORT="${PORT:-6788}"
STATE="${WATCHDOG_STATE:-$ROOT/backups/.watchdog.state}"
mkdir -p "$(dirname "$STATE")"; touch "$STATE"

problems=()
ready="$(curl -fsS -m 10 "http://localhost:$PORT/api/health/ready" 2>/dev/null || true)"
if [[ "$ready" != *'"status":"ok"'* ]]; then problems+=("api: /health/ready ishlamayapti (${ready:-javob yoq})")
elif [[ "$ready" != *'"worker":"ok"'* ]]; then problems+=("worker: yurak urishi yoq"); fi
use="$(df -P . | awk 'NR==2 {gsub("%","",$5); print $5}')"
[[ "$use" -lt 85 ]] || problems+=("disk $use% band")
latest="$(ls -1t backups/*.tar.gz* 2>/dev/null | grep -v '\.sha256$' | head -1 || true)"
if [[ -n "$latest" ]]; then
  age=$(( ( $(date +%s) - $(stat -c %Y "$latest" 2>/dev/null || stat -f %m "$latest") ) / 3600 ))
  [[ "$age" -le 30 ]] || problems+=("zaxira ${age} soat oldin (kunlik bo'lishi kerak)")
fi

send() {
  echo "$(date '+%F %T') $1"
  [[ -n "$TOKEN" && -n "$CHAT" ]] && curl -fsS -m 10 -o /dev/null "https://api.telegram.org/bot$TOKEN/sendMessage" --data-urlencode "chat_id=$CHAT" --data-urlencode "text=$1" || true
}
cur="$(printf '%s\n' "${problems[@]:-}" | sed '/^$/d' | sort)"
prev="$(cat "$STATE")"
if [[ "$cur" != "$prev" ]]; then
  if [[ -n "$cur" ]]; then send "⚠ ${CLIENT:-vaksina}: muammo
$cur"; else send "✔ ${CLIENT:-vaksina}: hammasi tiklandi"; fi
  printf '%s' "$cur" > "$STATE"
fi
