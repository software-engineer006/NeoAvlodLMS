#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
"$ROOT/scripts/agent_skills/docker_env.sh" node bash -c '
set -euo pipefail
# Production builds must not load a developer Vite env file.
if find . -path "*/node_modules" -prune -o -name ".env*" ! -name ".env.example" -print | grep -q .; then
  echo "Remove frontend .env files before preparing the reproducible release." >&2
  exit 1
fi
unset VITE_LOCAL_DEMO VITE_API_PROXY_TARGET
npm ci
npm run typecheck
npm run lint
npm test
npm run build
node prepare-release.mjs
'
