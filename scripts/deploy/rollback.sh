#!/usr/bin/env bash
# NeoAvlod LMS Release Rollback Script
set -euo pipefail

WEB_ROOT="${WEB_ROOT:-/var/www/neoavlod}"
APP_ROOT="${APP_ROOT:-/opt/neoavlod}"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://127.0.0.1:8000/api/v1/health}"
SKIP_RELOAD_NGINX="${SKIP_RELOAD_NGINX:-0}"
SKIP_DOCKER="${SKIP_DOCKER:-0}"

printf '==> Boshlanmoqda: Release Rollback...\n'

CURRENT_TARGET=""
if [[ -L "$WEB_ROOT/current" ]]; then
  CURRENT_TARGET="$(basename "$(readlink "$WEB_ROOT/current" || true)")"
fi

PREV_RELEASE=""
if [[ -f "$APP_ROOT/.previous_release" ]]; then
  PREV_RELEASE="$(cat "$APP_ROOT/.previous_release" | tr -d '[:space:]')"
fi

# Agar fayldagi release hozirgi target bilan bir xil bo'lsa yoki mavjud bo'lmasa,
# releases katalogidan CURRENT_TARGET dan farqli eng yangisini topish
if [[ -z "$PREV_RELEASE" || "$PREV_RELEASE" == "$CURRENT_TARGET" || ! -d "$WEB_ROOT/releases/$PREV_RELEASE" ]]; then
  PREV_RELEASE=""
  for rel in $(ls -1dt "$WEB_ROOT/releases"/* 2>/dev/null); do
    base="$(basename "$rel")"
    if [[ "$base" != "$CURRENT_TARGET" ]]; then
      PREV_RELEASE="$base"
      break
    fi
  done
fi

if [[ -z "$PREV_RELEASE" || ! -d "$WEB_ROOT/releases/$PREV_RELEASE" ]]; then
  printf 'XATO: Qaytish uchun avvalgi release topilmadi!\n' >&2
  exit 1
fi

printf '==> Tiklanayotgan avvalgi release: %s\n' "$PREV_RELEASE"

# 1. Simvolik havolalarni orqaga qaytarish
ln -sfn "releases/$PREV_RELEASE" "$WEB_ROOT/current"

ln -sfn "$WEB_ROOT/current/admin" "$WEB_ROOT/admin"
ln -sfn "$WEB_ROOT/current/teacher" "$WEB_ROOT/teacher"

# Kelgusi rollback uchun undan oldingi releaseni saqlash
NEXT_PREV=""
found_prev=false
for rel in $(ls -1dt "$WEB_ROOT/releases"/* 2>/dev/null); do
  base="$(basename "$rel")"
  if [[ "$found_prev" == true && "$base" != "$PREV_RELEASE" ]]; then
    NEXT_PREV="$base"
    break
  fi
  if [[ "$base" == "$PREV_RELEASE" ]]; then
    found_prev=true
  fi
done

if [[ -n "$NEXT_PREV" ]]; then
  echo "$NEXT_PREV" > "$APP_ROOT/.previous_release"
else
  rm -f "$APP_ROOT/.previous_release"
fi

# 2. Docker servislarni tiklash (agar kerak bo'lsa)
if [[ "$SKIP_DOCKER" == "0" && -f "$APP_ROOT/compose.prod.yaml" ]]; then
  printf '==> Docker konteynerlar qayta ishga tushirilmoqda...\n'
  docker compose -f "$APP_ROOT/compose.prod.yaml" --env-file "$APP_ROOT/.env.production" up -d --wait api worker
fi

# 3. Nginx qayta yuklash
if [[ "$SKIP_RELOAD_NGINX" == "0" ]] && command -v nginx >/dev/null 2>&1; then
  printf '==> Nginx qayta yuklanmoqda...\n'
  nginx -t
  if command -v systemctl >/dev/null 2>&1; then
    systemctl reload nginx || true
  else
    service nginx reload || true
  fi
fi

# 4. Rollback Health Check
printf '==> Rollback health check tekshirilmoqda...\n'
ROLLBACK_OK=false
for i in {1..15}; do
  if curl -sf "$HEALTH_CHECK_URL" >/dev/null 2>&1; then
    ROLLBACK_OK=true
    break
  fi
  sleep 1
done

if [[ "$ROLLBACK_OK" == "false" ]]; then
  printf 'OGOHLANTIRISH: Rollbackdan keyin health check javob bermadi!\n' >&2
else
  printf '==> Rollbackdan so‘ng health check muvaffaqiyatli o‘tdi.\n'
fi

printf '==> Rollback muvaffaqiyatli yakunlandi: Hozirgi aktiv release %s\n' "$PREV_RELEASE"
