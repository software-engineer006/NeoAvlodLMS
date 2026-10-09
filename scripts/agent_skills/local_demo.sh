#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
"$AGENT_ROOT/scripts/agent_skills/docker_env.sh" init
compose_local() {
  NEOAVLOD_UID="$(id -u)" NEOAVLOD_GID="$(id -g)" docker compose \
    --project-directory "$AGENT_ROOT" --env-file "$AGENT_ROOT/.env" \
    -f "$AGENT_ROOT/compose.yaml" -f "$AGENT_ROOT/compose.local.yaml" "$@"
}
case "${1:-up}" in
  up)
    compose_local build backend
    compose_local up -d --wait --wait-timeout 120 demo-database
    compose_local run --rm -T --no-deps migrations
    compose_local run --rm -T --no-deps node npm ci
    compose_local up -d --wait --wait-timeout 120 backend admin teacher worker
    printf 'Admin: http://localhost:3000\nTeacher: http://127.0.0.1:3001\n'
    ;;
  restart) compose_local up -d --no-build --wait --wait-timeout 120 backend admin teacher worker ;;
  status) compose_local ps ;;
  smoke) compose_local exec -T backend python /workspace/scripts/agent_skills/smoke_local_demo.py ;;
  stop) compose_local stop admin teacher worker backend demo-database ;;
  *) fail 'Buyruqlar: up, restart, status, smoke, stop' ;;
esac
