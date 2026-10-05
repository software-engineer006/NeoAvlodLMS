#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
enter_backend_container check_agent_skills.sh
for script in "$AGENT_ROOT"/scripts/agent_skills/*.sh; do
  bash -n "$script"
done
python3 -m unittest discover -s "$AGENT_ROOT/scripts/agent_skills/tests" -v
python3 "$AGENT_ROOT/scripts/agent_skills/task_manager.py" validate
