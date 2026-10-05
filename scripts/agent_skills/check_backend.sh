#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
[[ -f "$AGENT_ROOT/backend/pyproject.toml" ]] || fail 'Backend hali yaratilmagan.'
enter_backend_container check_backend.sh
backend_python
cd "$AGENT_ROOT/backend"
"$AGENT_PYTHON" -c 'import importlib.util, sys; missing = [m for m in ("ruff", "mypy", "pytest", "neoavlod") if importlib.util.find_spec(m) is None]; sys.exit("Yetishmayotgan modullar: " + ", ".join(missing) + "; install_backend.sh ni ishga tushiring" if missing else 0)'
targets=(src tests)
if [[ -d alembic ]]; then targets+=(alembic); fi
"$AGENT_PYTHON" -m compileall -q "${targets[@]}"
"$AGENT_PYTHON" -m ruff check "${targets[@]}" pyproject.toml
"$AGENT_PYTHON" -m mypy "${targets[@]}"
"$AGENT_PYTHON" -m pytest -q --tb=short
