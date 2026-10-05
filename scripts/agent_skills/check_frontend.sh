#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
[[ -f "$AGENT_ROOT/frontend/package.json" ]] || fail 'Frontend hali yaratilmagan (Task 026).'
if [[ "${NEOAVLOD_IN_DOCKER:-}" != 1 ]]; then
  exec "$AGENT_ROOT/scripts/agent_skills/docker_env.sh" node env NEOAVLOD_IN_DOCKER=1 bash /workspace/scripts/agent_skills/check_frontend.sh
fi
command -v node >/dev/null || fail 'Node.js kerak.'
command -v npm >/dev/null || fail 'npm kerak.'
cd "$AGENT_ROOT/frontend"
node -e 'const p=require("./package.json"); for (const s of ["typecheck","lint"]) if (!p.scripts?.[s]) { console.error(`Yetishmayotgan npm script: ${s}`); process.exit(1); }'
npm run typecheck
npm run lint
