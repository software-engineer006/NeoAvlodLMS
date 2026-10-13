#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
docker build -t neoavlod-browser:1.58.2 -f "$ROOT/scripts/agent_skills/Dockerfile.browser" "$ROOT/scripts/agent_skills"
docker run --rm --init --ipc=host --network neoavlod-dev_default \
  -v "$ROOT:/workspace" -w /workspace neoavlod-browser:1.58.2 node "$@"
