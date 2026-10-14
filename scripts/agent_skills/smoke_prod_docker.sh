#!/usr/bin/env bash
# One production fixture covers UID1000, readiness, roles, archival and rollback.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
exec "$AGENT_ROOT/scripts/agent_skills/smoke_release_deployment.sh" "$@"
