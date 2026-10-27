#!/usr/bin/env bash
# Production tayyorlik tekshiruvi: `make doctor`. ✘ bo'lsa 1 bilan chiqadi, ⚠ — tavsiya.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
BAD=0 WARN=0
ok()   { echo "  ✔ $*"; }
warn() { echo "  ⚠ $*"; WARN=$((WARN + 1)); }
bad()  { echo "  ✘ $*"; BAD=$((BAD + 1)); }
[[ -f .env ]] || { echo ".env topilmadi"; exit 1; }
get() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
len() { printf '%s' "$1" | wc -c | tr -d ' '; }

echo "Sirlar (.env)"
perm="$(stat -c '%a' .env 2>/dev/null || stat -f '%Lp' .env)"
[[ "$perm" == "600" ]] && ok ".env ruxsati 600" || warn ".env ruxsati $perm (chmod 600 .env)"
[[ "$(get ENV)" == "production" ]] && ok "ENV=production" || bad "ENV production emas (hozir: $(get ENV))"
SK="$(get SECRET_KEY)"; [[ "$(len "$SK")" -ge 32 && "$SK" != "change-me" && "$SK" != "__generate__" ]] && ok "SECRET_KEY kuchli" || bad "SECRET_KEY zaif/standart"
PP="$(get POSTGRES_PASSWORD)"; [[ "$(len "$PP")" -ge 16 && "$PP" != "vaksina" ]] && ok "POSTGRES_PASSWORD kuchli" || bad "POSTGRES_PASSWORD zaif/standart"
MP="$(get MINIO_ROOT_PASSWORD)"; [[ "$(len "$MP")" -ge 16 ]] && ok "MINIO_ROOT_PASSWORD kuchli" || bad "MINIO_ROOT_PASSWORD zaif"
LS="$(get LIVEKIT_API_SECRET)"; [[ "$(len "$LS")" -ge 32 ]] && ok "LIVEKIT_API_SECRET kuchli" || bad "LIVEKIT_API_SECRET qisqa/yo'q"
[[ -n "$(get FACE_ENCRYPTION_KEY)" ]] && ok "FACE_ENCRYPTION_KEY alohida berilgan" || warn "FACE_ENCRYPTION_KEY yo'q: SECRET_KEY dan olinadi (alohida qo'yish tavsiya etiladi)"
[[ -n "$(get BACKUP_PASSPHRASE)" ]] && ok "BACKUP_PASSPHRASE berilgan (arxivlar shifrlanadi)" || warn "BACKUP_PASSPHRASE yo'q: zaxira arxivlari shifrlanmaydi"

echo "Tarmoq"
[[ "$(get GATEWAY_BIND)" == "127.0.0.1" ]] && ok "gateway faqat 127.0.0.1 da" || bad "GATEWAY_BIND=$(get GATEWAY_BIND): gateway tashqariga ochiq (TLS yo'q!)"
PU="$(get PUBLIC_URL)"; [[ "$PU" == https://* ]] && ok "PUBLIC_URL https" || warn "PUBLIC_URL https:// emas ($PU)"
NIP="$(get LIVEKIT_NODE_IP)"; [[ -n "$NIP" && "$NIP" != "127.0.0.1" ]] && ok "LIVEKIT_NODE_IP=$NIP" || warn "LIVEKIT_NODE_IP lokal: qo'ng'iroqlar NAT ortida ishlamaydi"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q active; then
  ufw status | grep -q "6788" && bad "ufw: 6788 ochilgan" || ok "ufw faol, 6788 yopiq"
else warn "ufw faol emas yoki topilmadi (firewall ni qo'lda tekshiring)"; fi

echo "Xizmatlar"
if docker compose ps >/dev/null 2>&1; then
  for s in api worker db redis minio gateway frontend; do
    st="$(docker compose ps --format '{{.Service}} {{.Status}}' 2>/dev/null | awk -v s="$s" '$1==s {print $0}')"
    [[ "$st" == *"Up"* && "$st" != *"unhealthy"* ]] && ok "$s: ishlayapti" || bad "$s: ${st:-ishlamayapti}"
  done
  P="$(get GATEWAY_PORT)"; P="${P:-6788}"
  curl -fsS "http://localhost:$P/api/health/ready" | grep -q '"status":"ok"' && ok "/api/health/ready ok" || bad "/api/health/ready ok emas"
  [[ "$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$P/api/docs")" == "404" ]] && ok "/api/docs yopiq" || warn "/api/docs ochiq"
  [[ "$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$P/api/metrics")" == "404" ]] && ok "/api/metrics tashqaridan yopiq" || bad "/api/metrics tashqaridan ochiq"
else warn "docker compose ishlamayapti"; fi

echo "Zaxira va resurslar"
latest="$(ls -1t backups/*.tar.gz* 2>/dev/null | grep -v '\.sha256$' | head -1)"
if [[ -n "$latest" ]]; then
  age=$(( ( $(date +%s) - $(stat -c %Y "$latest" 2>/dev/null || stat -f %m "$latest") ) / 3600 ))
  [[ "$age" -le 26 ]] && ok "oxirgi zaxira $age soat oldin" || warn "oxirgi zaxira $age soat oldin (cron ishlayaptimi?)"
else warn "zaxira yo'q: make backup"; fi
use="$(df -P . | awk 'NR==2 {gsub("%","",$5); print $5}')"
[[ "$use" -lt 85 ]] && ok "disk band: $use%" || bad "disk band: $use%"
if [[ "$PU" == https://* ]] && command -v openssl >/dev/null 2>&1; then
  host="${PU#https://}"; host="${host%%/*}"
  end="$(echo | timeout 8 openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
  if [[ -n "$end" ]]; then
    days=$(( ( $(date -d "$end" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$end" +%s) - $(date +%s) ) / 86400 ))
    [[ "$days" -ge 14 ]] && ok "TLS sertifikat: $days kun qoldi" || warn "TLS sertifikat $days kundan keyin tugaydi"
  else warn "TLS sertifikatni tekshirib bo'lmadi ($host:443)"; fi
fi

echo
echo "Natija: $BAD ta ✘, $WARN ta ⚠"
[[ "$BAD" -eq 0 ]]
