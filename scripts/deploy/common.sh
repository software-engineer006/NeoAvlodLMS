#!/usr/bin/env bash
# Shared release operations; sourced by deploy/rollback/server entrypoints.
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/neoavlod}"
WEB_ROOT="${WEB_ROOT:-/var/www/neoavlod}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/neoavlod}"
ENV_FILE="${ENV_FILE:-$APP_ROOT/.env.production}"
NGINX_CONFIG_ROOT="${NGINX_CONFIG_ROOT:-/etc/nginx}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-neoavlod-prod}"
PORTAL_HTTPS_PORT="${PORTAL_HTTPS_PORT:-443}"
fail() { printf 'Xato: %s\n' "$*" >&2; return 1; }
valid_release() { [[ "$1" =~ ^[a-f0-9]{40}$ ]] || fail 'Release ID full Git SHA bo‘lishi kerak.'; }
lock_deploy() {
  mkdir -p "$APP_ROOT" "$WEB_ROOT/releases" "$BACKUP_ROOT"
  exec 9>"$APP_ROOT/.deploy.lock"
  flock -w 600 9 || fail 'Boshqa deployment tugamadi.'
}
compose_release() {
  local release="$1"; shift
  NEOAVLOD_RELEASE_ID="$release" docker compose -p "$COMPOSE_PROJECT_NAME" \
    --project-directory "$APP_ROOT/releases/$release" --env-file "$ENV_FILE" \
    -f "$APP_ROOT/releases/$release/compose.prod.yaml" "$@"
}
import_educenter() {
  local release="$1"
  local source_dir="${EDUCENTER_DATA_DIR:-$APP_ROOT/private/educenter_data}"
  local state_dir="$APP_ROOT/private/educenter-state"
  if [[ ! -d "$source_dir" ]]; then
    [[ -z "${EDUCENTER_DATA_DIR:-}" ]] || { fail 'EDUCENTER_DATA_DIR mavjud emas.'; return 1; }
    printf 'Educenter private data katalogi yo‘q; data import sozlanmagan.\n'
    return 0
  fi
  local expected
  [[ -f "$source_dir/plan.sha256" ]] || { fail 'Reviewed private plan.sha256 kerak.'; return 1; }
  expected="$(cat "$source_dir/plan.sha256")"
  [[ "$expected" =~ ^[a-f0-9]{64}$ ]] || { fail 'Import SHA256 noto‘g‘ri.'; return 1; }
  mkdir -p "$state_dir"
  chmod 700 "$state_dir"
  # Existing credentials can be securely copied into state_dir before first deployment.
  # Otherwise the CLI creates random passwords there, never in the Git release.
  compose_release "$release" run --rm -T --no-deps --user "$(id -u):$(id -g)" \
    -v "$source_dir:/import-source:ro" -v "$state_dir:/import-state" \
    migrations python -m neoavlod.educenter_import --source /import-source \
    --credentials /import-state/prepared-accounts.json --report /import-state/last-plan.json \
    --apply --expected-plan "$expected" </dev/null
}
atomic_link() {
  local target="$1" link="$2"
  ln -s "$target" "$link.next.$$" || return 1
  mv -Tf "$link.next.$$" "$link"
}
install_nginx() {
  local release="$1"
  install -d -m 755 "$NGINX_CONFIG_ROOT/snippets" "$NGINX_CONFIG_ROOT/conf.d" || return 1
  install -m 644 "$APP_ROOT/releases/$release/nginx/snippets/"*.conf "$NGINX_CONFIG_ROOT/snippets/" || return 1
  install -m 644 "$APP_ROOT/releases/$release/nginx/conf.d/eduneo.conf" "$NGINX_CONFIG_ROOT/conf.d/eduneo.conf" || return 1
  rm -f "$NGINX_CONFIG_ROOT/conf.d/neoavlod-acme.conf" || return 1
  nginx -t || return 1
  systemctl reload nginx || return 1
}
activate_links() {
  local release="$1"
  atomic_link "releases/$release" "$APP_ROOT/current" || return 1
  atomic_link "releases/$release" "$WEB_ROOT/current" || return 1
  for portal in admin teacher; do
    if [[ -e "$WEB_ROOT/$portal" && ! -L "$WEB_ROOT/$portal" ]]; then
      fail "$WEB_ROOT/$portal katalog; avval uni zaxiralab ko‘chiring."
      return 1
    fi
    atomic_link "current/$portal" "$WEB_ROOT/$portal" || return 1
  done
}
check_health() {
  local release="$1"
  compose_release "$release" exec -T api python -c 'import urllib.request; [urllib.request.urlopen("http://127.0.0.1:8000/api/v1/"+p, timeout=5) for p in ("health","ready")]' </dev/null || return 1
  [[ "$(compose_release "$release" ps --status running -q worker | wc -l | tr -d ' ')" == 1 ]] || { fail 'Bitta worker ishlashi kerak.'; return 1; }
  local portal host marker actual
  local tls_args=()
  [[ -z "${PORTAL_CA_FILE:-}" ]] || tls_args=(--cacert "$PORTAL_CA_FILE")
  for portal in admin teacher api; do
    host="$portal.eduneo.uz"
    curl --noproxy '*' --retry 5 --retry-delay 1 --retry-all-errors --fail --silent --show-error --max-time 10 "${tls_args[@]}" \
      --resolve "$host:$PORTAL_HTTPS_PORT:127.0.0.1" "https://$host:$PORTAL_HTTPS_PORT/api/v1/ready" >/dev/null || return 1
    if [[ "$portal" != api ]]; then
      actual="$(curl --noproxy '*' --fail --silent --show-error --max-time 10 "${tls_args[@]}" \
        --resolve "$host:$PORTAL_HTTPS_PORT:127.0.0.1" "https://$host:$PORTAL_HTTPS_PORT/release.txt")" || return 1
      [[ "$actual" == "$release" ]] || { fail "$portal frontend versiyasi yangilanmagan."; return 1; }
    fi
  done
}
restore_release() {
  local release="$1"
  valid_release "$release" || return 1
  [[ -f "$APP_ROOT/releases/$release/.successful" && -d "$WEB_ROOT/releases/$release" ]] || { fail 'Ishchi release topilmadi.'; return 1; }
  docker image inspect "neoavlod-backend:$release" >/dev/null || return 1
  compose_release "$release" up -d --no-deps --no-build --force-recreate --wait --wait-timeout 120 api worker || return 1
  activate_links "$release" || return 1
  install_nginx "$release" || return 1
  check_health "$release"
}
