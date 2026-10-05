#!/usr/bin/env bash
# NeoAvlod LMS Atomic Deployment Script
set -euo pipefail

RELEASE_ID="${1:?Usage: deploy.sh <release_id> [dist_source_dir]}"
DIST_SOURCE="${2:-}"

WEB_ROOT="${WEB_ROOT:-/var/www/neoavlod}"
APP_ROOT="${APP_ROOT:-/opt/neoavlod}"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://127.0.0.1:8000/api/v1/health}"
READY_CHECK_URL="${READY_CHECK_URL:-http://127.0.0.1:8000/api/v1/ready}"
SKIP_RELOAD_NGINX="${SKIP_RELOAD_NGINX:-0}"
SKIP_DOCKER="${SKIP_DOCKER:-0}"

printf '==> Boshlanmoqda: Release %s deployment...\n' "$RELEASE_ID"

# 1. Joriy va avvalgi release holatini aniqlash
mkdir -p "$WEB_ROOT/releases" "$APP_ROOT/releases"

PREV_RELEASE=""
if [[ -L "$WEB_ROOT/current" ]]; then
  PREV_TARGET="$(readlink "$WEB_ROOT/current" || true)"
  PREV_RELEASE="$(basename "$PREV_TARGET")"
  printf 'Avvalgi release aniqlandi: %s\n' "$PREV_RELEASE"
  echo "$PREV_RELEASE" > "$APP_ROOT/.previous_release"
fi

NEW_RELEASE_DIR="$WEB_ROOT/releases/$RELEASE_ID"
mkdir -p "$NEW_RELEASE_DIR/admin" "$NEW_RELEASE_DIR/teacher"

# 2. Yangi frontend statik fayllarini joylashtirish
if [[ -n "$DIST_SOURCE" && -d "$DIST_SOURCE" ]]; then
  if [[ -d "$DIST_SOURCE/admin/dist" ]]; then
    cp -r "$DIST_SOURCE/admin/dist/"* "$NEW_RELEASE_DIR/admin/"
  elif [[ -d "$DIST_SOURCE/admin" ]]; then
    cp -r "$DIST_SOURCE/admin/"* "$NEW_RELEASE_DIR/admin/"
  fi

  if [[ -d "$DIST_SOURCE/teacher/dist" ]]; then
    cp -r "$DIST_SOURCE/teacher/dist/"* "$NEW_RELEASE_DIR/teacher/"
  elif [[ -d "$DIST_SOURCE/teacher" ]]; then
    cp -r "$DIST_SOURCE/teacher/"* "$NEW_RELEASE_DIR/teacher/"
  fi
fi

# Agar index.html bo'lmasa, minimal fallback yaratish (test/fallback uchun)
[[ -f "$NEW_RELEASE_DIR/admin/index.html" ]] || echo '<!doctype html><html><body><div id="root">Admin</div></body></html>' > "$NEW_RELEASE_DIR/admin/index.html"
[[ -f "$NEW_RELEASE_DIR/teacher/index.html" ]] || echo '<!doctype html><html><body><div id="root">Teacher</div></body></html>' > "$NEW_RELEASE_DIR/teacher/index.html"

# 3. Docker va migratsiyalar (agar yoqilgan bo'lsa)
if [[ "$SKIP_DOCKER" == "0" && -f "$APP_ROOT/compose.prod.yaml" ]]; then
  printf '==> Docker migratsiyalari va konteynerlar yangilanmoqda...\n'
  docker compose -f "$APP_ROOT/compose.prod.yaml" --env-file "$APP_ROOT/.env.production" run --rm migrations
  docker compose -f "$APP_ROOT/compose.prod.yaml" --env-file "$APP_ROOT/.env.production" up -d --wait api worker
fi

# 4. Atomik simvolik havolani yangilash
printf '==> Atomik symlink yangilanmoqda...\n'
ln -sfn "releases/$RELEASE_ID" "$WEB_ROOT/current"

# Subdomenlar uchun qat'iy havolalar
ln -sfn "$WEB_ROOT/current/admin" "$WEB_ROOT/admin"
ln -sfn "$WEB_ROOT/current/teacher" "$WEB_ROOT/teacher"

# 5. Nginx qayta yuklash
if [[ "$SKIP_RELOAD_NGINX" == "0" ]] && command -v nginx >/dev/null 2>&1; then
  printf '==> Nginx konfiguratsiyasi tekshirilmoqda va qayta yuklanmoqda...\n'
  nginx -t
  if command -v systemctl >/dev/null 2>&1; then
    systemctl reload nginx || true
  else
    service nginx reload || true
  fi
fi

# 6. Post-deployment Health Check
printf '==> Post-deployment health check tekshirilmoqda...\n'
HEALTH_OK=false
for i in {1..20}; do
  if curl -sf "$HEALTH_CHECK_URL" >/dev/null 2>&1; then
    if [[ -z "$READY_CHECK_URL" ]] || curl -sf "$READY_CHECK_URL" >/dev/null 2>&1; then
      HEALTH_OK=true
      break
    fi
  fi
  sleep 1
done

if [[ "$HEALTH_OK" == "false" ]]; then
  printf 'XATO: Post-deployment health check muvaffaqiyatsiz tugadi!\n' >&2
  printf '==> Avtomatik ROLLBACK boshlanmoqda...\n' >&2
  rm -rf "$NEW_RELEASE_DIR"
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  "$SCRIPT_DIR/rollback.sh"
  exit 1
fi

# 7. Eski releaselarni tozalash (oxirgi 5 ta saqlanadi)
printf '==> Eski releaselar tozalanmoqda...\n'
(
  cd "$WEB_ROOT/releases"
  ls -1dt ./* 2>/dev/null | tail -n +6 | xargs -I {} rm -rf "{}" 2>/dev/null || true
)

printf '==> Deployment muvaffaqiyatli yakunlandi: Release %s aktiv.\n' "$RELEASE_ID"
