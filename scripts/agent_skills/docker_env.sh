#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

init_env() {
  if [[ ! -f "$AGENT_ROOT/.env" ]]; then
    local password
    password="$(openssl rand -hex 32)"
    (umask 077; printf 'POSTGRES_USER=neoavlod\nPOSTGRES_DB=neoavlod\nPOSTGRES_PASSWORD=%s\nAPI_PORT=8000\n' "$password" > "$AGENT_ROOT/.env")
    printf 'Local .env yaratildi; secret yashirildi.\n'
  fi
  for key in NEOAVLOD_SECURITY_SECRET NEOAVLOD_BOT_ENCRYPTION_KEY; do
    local present=false line value
    while IFS= read -r line; do
      if [[ "$line" == "$key="* && -n "${line#*=}" ]]; then present=true; fi
    done < "$AGENT_ROOT/.env"
    if [[ "$present" == false ]]; then
      if [[ "$key" == NEOAVLOD_SECURITY_SECRET ]]; then
        value="$(openssl rand -hex 32)"
      else
        value="$(openssl rand -base64 32 | tr '/+' '_-')"
      fi
      printf '%s=%s\n' "$key" "$value" >> "$AGENT_ROOT/.env"
      chmod 600 "$AGENT_ROOT/.env"
    fi
  done
}

compose() {
  NEOAVLOD_UID="$(id -u)" NEOAVLOD_GID="$(id -g)" docker compose --project-directory "$AGENT_ROOT" --env-file "$AGENT_ROOT/.env" -f "$AGENT_ROOT/compose.yaml" "$@"
}

action="${1:-status}"
shift || true
init_env
command -v docker >/dev/null || fail 'Docker kerak; host runtimega fallback yo‘q.'
docker info >/dev/null 2>&1 || fail 'Docker daemon ishlamayapti yoki unga ruxsat yo‘q.'
case "$action" in
  init) compose config --quiet ;;
  build) compose build --pull backend ;;
  restart) compose up -d --no-build --wait --wait-timeout 120 backend ;;
  up)
    compose config --quiet
    compose build backend
    compose up -d --wait --wait-timeout 180 backend test-database
    ;;
  exec)
    compose up -d --wait --wait-timeout 120 test-database
    compose run --rm -T --no-deps tools "$@"
    ;;
  task) compose run --rm -T --no-deps tools python /workspace/scripts/agent_skills/task_manager.py "$@" ;;
  node) compose run --rm -T --no-deps node "$@" ;;
  migrate)
    compose up -d --wait --wait-timeout 120 database
    compose run --rm -T --no-deps migrations
    ;;
  dbexec)
    compose up -d --wait --wait-timeout 120 database
    compose run --rm -T --no-deps migrations "$@"
    ;;
  bootstrap)
    compose up -d --wait --wait-timeout 120 database
    compose run --rm --no-deps migrations python -m neoavlod.cli bootstrap "$@"
    ;;
  smoke)
    compose exec -T backend python -c "import json, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health'); assert r.status == 200; print(json.loads(r.read()))"
    compose exec -T backend python -c "import json, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready'); assert r.status == 200; print(json.loads(r.read()))"
    compose exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SHOW server_version"'
    ;;
  status) compose ps ;;
  stop) compose stop ;;
  *) fail 'Buyruqlar: init, build, restart, up, exec, task, node, migrate, dbexec, bootstrap, smoke, status, stop' ;;
esac
