#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
RELEASE_ID="${1:?Usage: deploy.sh <full_git_sha>}"
valid_release "$RELEASE_ID"
lock_deploy
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
[[ -f "$ENV_FILE" && -f "$RELEASE_DIR/compose.prod.yaml" ]] || fail 'Release source yoki production env yo‘q.'
for portal in admin teacher; do
  [[ -s "$RELEASE_DIR/frontend/release/$portal/index.html" ]] || fail "$portal production build yo‘q; fallback yaratilmaydi."
  [[ ! -e "$WEB_ROOT/$portal" || -L "$WEB_ROOT/$portal" ]] || fail "$WEB_ROOT/$portal katalog; avval uni zaxiralab ko‘chiring."
done
PREVIOUS=""
[[ ! -L "$APP_ROOT/current" ]] || PREVIOUS="$(basename "$(readlink "$APP_ROOT/current")")"
if [[ "$PREVIOUS" == "$RELEASE_ID" ]]; then
  check_health "$RELEASE_ID"
  printf 'Release allaqachon ishlayapti: %s\n' "$RELEASE_ID"
  exit 0
fi
NGINX_BACKUP="$(mktemp -d "$APP_ROOT/.nginx-before.XXXXXX")"
cp -a "$NGINX_CONFIG_ROOT/conf.d" "$NGINX_BACKUP/conf.d"
cp -a "$NGINX_CONFIG_ROOT/snippets" "$NGINX_BACKUP/snippets"
RUNTIME_TOUCHED=0
rollback_on_error() {
  local result=$?
  trap - ERR
  set +e
  printf 'Deployment muvaffaqiyatsiz; oldingi release tiklanmoqda.\n' >&2
  if [[ -n "$PREVIOUS" && "$RUNTIME_TOUCHED" == 1 ]]; then
    if ! restore_release "$PREVIOUS"; then
      printf 'ROLLBACK HAM MUVAFFAQIYATSIZ: serverni tekshiring.\n' >&2
    fi
  else
    cp -a "$NGINX_BACKUP/conf.d/." "$NGINX_CONFIG_ROOT/conf.d/"
    cp -a "$NGINX_BACKUP/snippets/." "$NGINX_CONFIG_ROOT/snippets/"
    if [[ ! -f "$NGINX_BACKUP/conf.d/eduneo.conf" ]]; then rm -f "$NGINX_CONFIG_ROOT/conf.d/eduneo.conf"; fi
    nginx -t && systemctl reload nginx
    if [[ "$RUNTIME_TOUCHED" == 1 && -z "$PREVIOUS" ]]; then
      compose_release "$RELEASE_ID" stop api worker
      rm -f "$APP_ROOT/current" "$WEB_ROOT/current" "$WEB_ROOT/admin" "$WEB_ROOT/teacher"
      printf 'Birinchi deploy xato: avvalgi release yo‘q, yangi API/worker to‘xtatildi.\n' >&2
    fi
  fi
  rm -rf "$NGINX_BACKUP"
  exit "$result"
}
trap rollback_on_error ERR
# Validate actual asset checksums in Docker before changing runtime state.
compose_release "$RELEASE_ID" build api
compose_release "$RELEASE_ID" run --rm -T --no-deps \
  -v "$RELEASE_DIR/frontend:/frontend:ro" -v "$RELEASE_DIR/scripts/deploy:/deploy:ro" \
  migrations python /deploy/verify_frontend.py /frontend </dev/null
WEB_RELEASE="$WEB_ROOT/releases/$RELEASE_ID"
[[ ! -e "$WEB_RELEASE" ]] || rm -rf "$WEB_RELEASE"
mkdir -p "$WEB_RELEASE"
cp -a "$RELEASE_DIR/frontend/release/admin" "$RELEASE_DIR/frontend/release/teacher" "$WEB_RELEASE/"
for portal in admin teacher; do printf '%s\n' "$RELEASE_ID" > "$WEB_RELEASE/$portal/release.txt"; done
chmod -R a+rX "$WEB_RELEASE"
compose_release "$RELEASE_ID" up -d --wait --wait-timeout 120 database
# Always back up before applying migrations. Failed pg_dump leaves no usable backup.
BACKUP="$BACKUP_ROOT/pre-$RELEASE_ID-$(date -u +%Y%m%dT%H%M%SZ).dump"
umask 077
compose_release "$RELEASE_ID" exec -T database sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' </dev/null > "$BACKUP.partial"
[[ -s "$BACKUP.partial" ]]
mv "$BACKUP.partial" "$BACKUP"
# Stop old application writers across migrations and replace both services with the exact image.
RUNTIME_TOUCHED=1
compose_release "$RELEASE_ID" stop api worker
compose_release "$RELEASE_ID" run --rm -T --no-deps migrations </dev/null
compose_release "$RELEASE_ID" up -d --no-deps --no-build --force-recreate --wait --wait-timeout 120 api worker
activate_links "$RELEASE_ID"
install_nginx "$RELEASE_ID"
check_health "$RELEASE_ID"
[[ -z "$PREVIOUS" ]] || printf '%s\n' "$PREVIOUS" > "$APP_ROOT/.previous_release"
touch "$RELEASE_DIR/.successful"
rm -rf "$NGINX_BACKUP"
trap - ERR
printf 'Backend + admin + teacher deployment tekshirildi: %s\n' "$RELEASE_ID"
# Release/image pruning is manual: keep rollback pairs and backups intact.
