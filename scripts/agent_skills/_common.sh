#!/usr/bin/env bash
# Shared paths; source this file from the executable entry points.
set -euo pipefail
AGENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

fail() { printf 'Xato: %s\n' "$*" >&2; exit 1; }

backend_python() {
  [[ "${NEOAVLOD_IN_DOCKER:-}" == 1 ]] || fail 'Python faqat Dockerda bajarilishi kerak.'
  if [[ -n "${BACKEND_PYTHON:-}" ]]; then
    AGENT_PYTHON="$BACKEND_PYTHON"
  elif [[ -x /opt/venv/bin/python ]]; then
    AGENT_PYTHON=/opt/venv/bin/python
  else
    AGENT_PYTHON="$(command -v python3)" || fail 'Python 3 topilmadi.'
  fi
}

enter_backend_container() {
  if [[ "${NEOAVLOD_IN_DOCKER:-}" != 1 ]]; then
    exec "$AGENT_ROOT/scripts/agent_skills/docker_env.sh" exec bash "/workspace/scripts/agent_skills/$1"
  fi
}
