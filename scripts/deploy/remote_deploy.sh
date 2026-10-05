#!/usr/bin/env bash
set -euo pipefail
: "${SSH_HOST:?SSH_HOST kerak}" "${SSH_USER:?SSH_USER kerak}" "${RELEASE_ID:?RELEASE_ID kerak}"
[[ "$RELEASE_ID" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid SHA' >&2; exit 1; }
[[ "${SSH_PORT:-22}" =~ ^[0-9]+$ ]] || exit 1
ssh -p "${SSH_PORT:-22}" -o StrictHostKeyChecking=yes -o BatchMode=yes \
  -o IdentitiesOnly=yes -i "$HOME/.ssh/neoavlod_ci" "$SSH_USER@$SSH_HOST" "deploy $RELEASE_ID"
