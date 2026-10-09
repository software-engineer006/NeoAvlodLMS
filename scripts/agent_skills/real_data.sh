#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
compose_local() {
  NEOAVLOD_UID="$(id -u)" NEOAVLOD_GID="$(id -g)" docker compose \
    --project-directory "$AGENT_ROOT" --env-file "$AGENT_ROOT/.env" \
    -f "$AGENT_ROOT/compose.yaml" -f "$AGENT_ROOT/compose.local.yaml" "$@"
}
private_dir="$AGENT_ROOT/.private/real-data"
counts_sql='SELECT json_build_object('\''staff'\'',(SELECT count(*) FROM staff),'\''groups'\'',(SELECT count(*) FROM groups),'\''students'\'',(SELECT count(*) FROM students),'\''parents'\'',(SELECT count(*) FROM parents),'\''attendance'\'',(SELECT count(*) FROM attendance),'\''outbox'\'',(SELECT count(*) FROM notification_outbox));'
case "${1:-status}" in
  backup)
    umask 077
    mkdir -p "$private_dir/backup"
    backup_name="${2:-pre-real-data}"
    [[ "$backup_name" =~ ^[a-z0-9-]+$ ]] || fail 'Backup nomi noto‘g‘ri.'
    dump="$private_dir/backup/$backup_name.dump"
    [[ ! -e "$dump" ]] || fail 'Backup mavjud; qayta yozilmaydi.'
    compose_local exec -T demo-database sh -c 'pg_dump -U "$POSTGRES_USER" -d neoavlod_demo -Fc' > "$dump"
    compose_local exec -T demo-database sh -c 'psql -U "$POSTGRES_USER" -d neoavlod_demo -tAc "$1"' sh "$counts_sql" > "$dump.counts"
    # createdb refuses an existing DB; only this newly created scratch DB is removed.
    compose_local exec -T demo-database sh -c 'createdb -U "$POSTGRES_USER" neoavlod_restore_check'
    trap 'compose_local exec -T demo-database sh -c '\''dropdb -U "$POSTGRES_USER" neoavlod_restore_check'\''' EXIT
    compose_local exec -T demo-database sh -c 'pg_restore -U "$POSTGRES_USER" -d neoavlod_restore_check --exit-on-error' < "$dump"
    compose_local exec -T demo-database sh -c 'psql -U "$POSTGRES_USER" -d neoavlod_restore_check -tAc "$1"' sh "$counts_sql" > "$dump.restored-counts"
    cmp "$dump.counts" "$dump.restored-counts"
    shasum -a 256 "$dump" > "$dump.sha256"
    printf 'Restore verified; source/restore counts match.\n' > "$dump.verified"
    cat "$dump.counts"
    printf 'Backup/restore verified; private dump retained.\n'
    ;;
  migrate) compose_local run --rm -T --no-deps migrations ;;
  exec) shift; compose_local run --rm -T --no-deps migrations "$@" ;;
  restart) compose_local up -d --no-build --wait --wait-timeout 120 backend admin teacher worker ;;
  status) compose_local ps ;;
  *) fail 'Buyruqlar: backup, migrate, exec, restart, status' ;;
esac
