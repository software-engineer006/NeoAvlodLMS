#!/usr/bin/env bash
# Install root-owned at /opt/neoavlod/bin; only this forced command accepts the CI key.
set -euo pipefail
REQUEST="${SSH_ORIGINAL_COMMAND:-}"
if [[ "$REQUEST" =~ ^deploy\ ([a-f0-9]{40})$ ]]; then
  exec bash /opt/neoavlod/bin/server_deploy.sh "${BASH_REMATCH[1]}"
elif [[ "$REQUEST" == rollback ]]; then
  exec bash /opt/neoavlod/current/scripts/deploy/rollback.sh
else
  printf 'Faqat deploy <full_sha> yoki rollback ruxsat etilgan.\n' >&2
  exit 1
fi
