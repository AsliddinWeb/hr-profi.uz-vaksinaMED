#!/usr/bin/env bash
# Chiqarish arxivi (git bo'lmagan holat uchun): sirlarsiz kod arxivi + SHA-256.
#   deploy/scripts/pack.sh        ->  dist/vaksinahr-<versiya>.tar.gz
# .env, zaxiralar, node_modules, kesh va skrinshotlar arxivga kirmaydi.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
VER="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' core/backend/app/__init__.py)"
[[ -n "$VER" ]] || { echo "Versiya topilmadi" >&2; exit 1; }
mkdir -p dist
OUT="dist/vaksinahr-${VER}.tar.gz"
tar -czf "$OUT" \
  --exclude='./dist' --exclude='./backups' --exclude='./screenshots' --exclude='./ui' --exclude='./.git' \
  --exclude='./.env' --exclude='./.env.*' --exclude='*/.env' \
  --exclude='node_modules' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' --exclude='.venv' --exclude='.DS_Store' \
  --exclude='core/frontend/dist' --exclude='*.log' --exclude='*.tsbuildinfo' \
  --transform "s,^\./,vaksinahr-${VER}/," ./ 2>/dev/null || tar -czf "$OUT" --exclude='./dist' --exclude='./backups' --exclude='./screenshots' --exclude='./ui' --exclude='./.env' --exclude='node_modules' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' --exclude='.DS_Store' --exclude='*.tsbuildinfo' ./
( cd dist && shasum -a 256 "vaksinahr-${VER}.tar.gz" > "vaksinahr-${VER}.tar.gz.sha256" )
if tar -tzf "$OUT" | grep -qE '(^|/)\.env$'; then echo "XATO: arxivga .env tushib qoldi" >&2; rm -f "$OUT"; exit 1; fi
echo "Tayyor: $OUT ($(du -h "$OUT" | cut -f1))"
cat "dist/vaksinahr-${VER}.tar.gz.sha256"
