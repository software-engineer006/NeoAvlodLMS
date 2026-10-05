#!/usr/bin/env bash
# Operator wrapper: always selects the current release's image and stable database volume.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
RELEASE="$(basename "$(readlink "$APP_ROOT/current")")"
valid_release "$RELEASE"
compose_release "$RELEASE" "$@"
