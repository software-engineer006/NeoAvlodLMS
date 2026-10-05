#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
[[ -f "$AGENT_ROOT/backend/alembic.ini" ]] || fail 'Alembic hali yaratilmagan (Task 007).'
if [[ "${NEOAVLOD_IN_DOCKER:-}" != 1 ]]; then
  exec "$AGENT_ROOT/scripts/agent_skills/docker_env.sh" migrate
fi
backend_python
cd "$AGENT_ROOT/backend"
"$AGENT_PYTHON" - <<'PY'
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

config = Config("alembic.ini")
heads = ScriptDirectory.from_config(config).get_heads()
if len(heads) != 1:
    raise SystemExit(f"Aynan bitta Alembic head kerak; topildi: {len(heads)}")
command.upgrade(config, "head")
command.current(config, check_heads=True, verbose=True)
command.check(config)
print("OK: upgrade head va model/migration mosligi tekshirildi")
PY
