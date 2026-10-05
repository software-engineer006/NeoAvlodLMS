#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
lock_deploy
CURRENT="$(basename "$(readlink "$APP_ROOT/current")")"
TARGET="${1:-$(cat "$APP_ROOT/.previous_release")}"
TARGET="${TARGET//[[:space:]]/}"
valid_release "$TARGET"
[[ "$TARGET" != "$CURRENT" ]] || fail 'Hozirgi release rollback target bo‘la olmaydi.'
restore_release "$TARGET"
printf '%s\n' "$CURRENT" > "$APP_ROOT/.previous_release"
printf 'Backend va ikkala frontend tiklandi: %s\n' "$TARGET"
