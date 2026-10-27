#!/usr/bin/env bash
# DigitalOcean Ubuntu droplet uchun birinchi sozlash (root sifatida): firewall, nginx, certbot, docker.
# Ishlatish: sudo deploy/scripts/droplet-setup.sh
set -euo pipefail

apt-get update
apt-get install -y ca-certificates curl ufw nginx certbot python3-certbot-nginx

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

# Firewall: SSH + web. 6788 TASHQARIGA OCHILMAYDI (faqat 127.0.0.1 da).
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
# Qo'ng'iroq (LiveKit, F25 da ishlatiladi): TCP fallback va bitta UDP media porti
ufw allow 7881/tcp
ufw allow 7882/udp
ufw --force enable

echo "Tayyor. Keyingi: deploy/host-nginx.conf.example ni sozlang va certbot --nginx -d <domen> ni ishga tushiring."
