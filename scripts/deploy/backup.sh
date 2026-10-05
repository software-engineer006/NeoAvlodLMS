#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
lock_deploy
RELEASE="$(basename "$(readlink "$APP_ROOT/current")")"
valid_release "$RELEASE"
umask 077
FILE="$BACKUP_ROOT/db-$(date -u +%Y%m%dT%H%M%SZ).dump"
compose_release "$RELEASE" exec -T database sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' </dev/null > "$FILE.partial"
[[ -s "$FILE.partial" ]]
mv "$FILE.partial" "$FILE"
printf 'Backup tayyor: %s\n' "$FILE"
