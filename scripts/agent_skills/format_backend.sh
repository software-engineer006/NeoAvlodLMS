#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
enter_backend_container format_backend.sh
backend_python
cd "$AGENT_ROOT/backend"
targets=(src tests)
if [[ -d alembic ]]; then targets+=(alembic); fi
"$AGENT_PYTHON" -m ruff format "${targets[@]}"
"$AGENT_PYTHON" -m ruff check --fix "${targets[@]}" pyproject.toml
