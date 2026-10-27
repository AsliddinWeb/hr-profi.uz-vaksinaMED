#!/usr/bin/env bash
# Yangi mijoz yaratadi: clients/<nom>/ skeleti (+ ixtiyoriy: .env, host nginx konfiguratsiyasi) va tekshiradi.
#
# Ishlatish:
#   deploy/scripts/new-client.sh <nom> ["Brend nomi"] [--domain hr.acme.uz] [--primary "#hex"] [--accent "#hex"]
#                                [--timezone Asia/Tashkent] [--off modul1,modul2] [--env] [--node-ip 1.2.3.4]
#
#   --domain    PUBLIC_URL va host nginx konfiguratsiyasini (clients/<nom>/host-nginx.conf) yaratadi
#   --env       .env yaratadi (tasodifiy sirlar bilan; mavjud .env ga TEGILMAYDI)
#   --node-ip   LiveKit uchun serverning ochiq IP si (qo'ng'iroqlar NAT ortida ishlashi uchun)
#   --off       shu modullarni o'chiradi (masalan: logistics,warehouse)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-1}"; }

NAME="" BRAND="" DOMAIN="" PRIMARY="" ACCENT="" TZ_NAME="" OFF="" MAKE_ENV=0 NODE_IP=""
POS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --domain) DOMAIN="${2:?--domain qiymati kerak}"; shift 2 ;;
    --primary) PRIMARY="${2:?}"; shift 2 ;;
    --accent) ACCENT="${2:?}"; shift 2 ;;
    --timezone) TZ_NAME="${2:?}"; shift 2 ;;
    --off) OFF="${2:?}"; shift 2 ;;
    --node-ip) NODE_IP="${2:?}"; shift 2 ;;
    --env) MAKE_ENV=1; shift ;;
    -*) echo "Noma'lum parametr: $1" >&2; usage ;;
    *) POS+=("$1"); shift ;;
  esac
done
NAME="${POS[0]:-}"; BRAND="${POS[1]:-}"
[[ -n "$NAME" ]] || usage

if [[ ! "$NAME" =~ ^[a-z][a-z0-9_-]{1,30}$ ]]; then
  echo "Nom: kichik lotin harf, raqam, '-' yoki '_' (2-31 belgi), harf bilan boshlanishi kerak" >&2; exit 1
fi
for pair in "primary:$PRIMARY" "accent:$ACCENT"; do
  v="${pair#*:}"
  if [[ -n "$v" && ! "$v" =~ ^#[0-9a-fA-F]{6}$ ]]; then echo "--${pair%%:*} '#rrggbb' bo'lishi kerak" >&2; exit 1; fi
done
if [[ -n "$DOMAIN" && ! "$DOMAIN" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$ ]]; then
  echo "--domain noto'g'ri: $DOMAIN" >&2; exit 1
fi

DEST="$ROOT/clients/$NAME"
[[ ! -e "$DEST" ]] || { echo "clients/$NAME allaqachon mavjud" >&2; exit 1; }
[[ -d "$ROOT/clients/_template" ]] || { echo "clients/_template topilmadi" >&2; exit 1; }
BRAND="${BRAND:-$NAME HR}"

# sed almashtirish matni uchun maxsus belgilarni himoyalash
esc() { printf '%s' "$1" | sed -e 's/[\/&|]/\\&/g'; }
subst() { # fayl... — __NAME__/__BRAND__ ni almashtiradi
  for f in "$@"; do
    sed -i.bak -e "s|__NAME__|$(esc "$NAME")|g" -e "s|__BRAND__|$(esc "$BRAND")|g" "$f"
    rm -f "$f.bak"
  done
}

cp -R "$ROOT/clients/_template" "$DEST"
subst "$DEST/client.yaml" "$DEST/backend_ext/__init__.py" "$DEST/frontend_ext/index.tsx" "$DEST/README.md"

[[ -z "$PRIMARY" ]] || sed -i.bak "s|primary: \"#[0-9a-fA-F]*\"|primary: \"$PRIMARY\"|" "$DEST/client.yaml"
[[ -z "$ACCENT" ]] || sed -i.bak "s|accent: \"#[0-9a-fA-F]*\"|accent: \"$ACCENT\"|" "$DEST/client.yaml"
[[ -z "$TZ_NAME" ]] || sed -i.bak "s|timezone: .*|timezone: $TZ_NAME|" "$DEST/client.yaml"
if [[ -n "$OFF" ]]; then
  IFS=',' read -ra MODS <<< "$OFF"
  for m in "${MODS[@]}"; do
    m="${m// /}"
    # shablondagi izohni ochamiz, bo'lmasa qo'shamiz
    if grep -q "^  # $m: false" "$DEST/client.yaml"; then
      sed -i.bak "s|^  # $m: false|  $m: false|" "$DEST/client.yaml"
    else
      sed -i.bak "s|^modules:|modules:\n  $m: false|" "$DEST/client.yaml"
    fi
  done
fi
rm -f "$DEST"/client.yaml.bak

# Mijozning .env namunasi (sirlarsiz) — serverda `cp` qilib to'ldiriladi
sed -e "s|^CLIENT_NAME=.*|CLIENT_NAME=$NAME|" ${DOMAIN:+-e "s|^PUBLIC_URL=.*|PUBLIC_URL=https://$DOMAIN|"} "$ROOT/.env.example" > "$DEST/.env.example"

if [[ -n "$DOMAIN" ]]; then
  sed -e "s|client1.vaksinahr.uz|$DOMAIN|g" "$ROOT/deploy/host-nginx.conf.example" > "$DEST/host-nginx.conf"
fi

if [[ "$MAKE_ENV" == 1 ]]; then
  if [[ -e "$ROOT/.env" ]]; then
    echo "OGOHLANTIRISH: .env mavjud, tegilmadi. Qo'lda CLIENT_NAME=$NAME qiling." >&2
  else
    cp "$DEST/.env.example" "$ROOT/.env"
    for k in SECRET_KEY POSTGRES_PASSWORD MINIO_ROOT_PASSWORD LIVEKIT_API_SECRET; do
      sed -i.bak "s|^$k=__generate__|$k=$(openssl rand -hex 24)|" "$ROOT/.env"
    done
    [[ -z "$NODE_IP" ]] || sed -i.bak "s|^LIVEKIT_NODE_IP=.*|LIVEKIT_NODE_IP=$NODE_IP|" "$ROOT/.env"
    sed -i.bak "s|^# FACE_ENCRYPTION_KEY=.*|FACE_ENCRYPTION_KEY=$(openssl rand -base64 36 | tr -d '\n')|" "$ROOT/.env"
    rm -f "$ROOT/.env.bak"
    chmod 600 "$ROOT/.env"
    echo ".env yaratildi (chmod 600). MUHIM: SECRET_KEY va FACE_ENCRYPTION_KEY ni xavfsiz joyda saqlang: ularsiz zaxiradan tiklab bo'lmaydi."
  fi
fi

# Sxema bo'yicha tekshiruv (docker va api imidji bo'lsa)
if command -v docker >/dev/null && docker image inspect vaksinahr-api >/dev/null 2>&1; then
  docker run --rm --entrypoint python -v "$DEST:/clients/$NAME:ro" -e CLIENT_DIR="/clients/$NAME" vaksinahr-api -m app.cli validate-client "/clients/$NAME" \
    || { echo "client.yaml xatolarini tuzating, so'ng: make validate-client CLIENT=$NAME" >&2; exit 1; }
else
  echo "(sxema tekshiruvi o'tkazib yuborildi: api imidji yo'q; keyin: make validate-client CLIENT=$NAME)"
fi

echo
echo "Yaratildi: clients/$NAME  (brend: $BRAND)"
echo "Keyingi qadamlar (to'liq ro'yxat: docs/NEW-CLIENT.md):"
echo "  1) clients/$NAME/client.yaml da brend va modullarni sozlang"
if [[ "$MAKE_ENV" == 1 ]]; then
  echo "  2) .env tayyor (CLIENT_NAME=$NAME)"
else
  echo "  2) .env yarating: make init, so'ng CLIENT_NAME=$NAME qiling (yoki --env bilan qayta yarating)"
fi
echo "  3) make up            # build + migratsiya + ishga tushirish"
echo "  4) make admin         # birinchi Ta'sischi (parol bir marta ko'rsatiladi)"
echo "  5) make smoke         # sog'liq tekshiruvi"
if [[ -n "$DOMAIN" ]]; then
  echo "  6) host nginx: clients/$NAME/host-nginx.conf -> /etc/nginx/sites-available/$DOMAIN, so'ng: certbot --nginx -d $DOMAIN"
fi
echo "  7) make backup        # birinchi zaxira + cron (docs/BACKUP.md)"
