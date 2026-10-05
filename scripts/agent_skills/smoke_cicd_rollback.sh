#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
if [[ "${NEOAVLOD_IN_DOCKER:-}" != 1 ]]; then
  docker run --rm -v "$AGENT_ROOT:/repo:ro" -w /repo rhysd/actionlint:1.7.11 -shellcheck= .github/workflows/ci-cd.yaml
  exec "$AGENT_ROOT/scripts/agent_skills/docker_env.sh" exec bash /workspace/scripts/agent_skills/smoke_cicd_rollback.sh
fi
python -m unittest discover -s "$AGENT_ROOT/scripts/deploy/tests" -v
