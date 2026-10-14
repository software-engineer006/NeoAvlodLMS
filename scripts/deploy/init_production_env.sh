#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/neoavlod}"
FILE="$APP_ROOT/.env.production"
mkdir -p "$APP_ROOT"
if [[ ! -e "$FILE" ]]; then
DB_PASSWORD="$(openssl rand -hex 32)"
SECURITY_KEY="$(openssl rand -hex 32)"
FERNET_KEY="$(openssl rand -base64 32 | tr '/+' '_-')"
umask 077
# noclobber protects secrets from concurrent initialization.
set -o noclobber
cat > "$FILE" <<ENV
POSTGRES_USER=neoavlod
POSTGRES_DB=neoavlod
POSTGRES_PASSWORD=$DB_PASSWORD
API_PORT=8000
NEOAVLOD_DATABASE_URL=postgresql+asyncpg://neoavlod:$DB_PASSWORD@database:5432/neoavlod
NEOAVLOD_SECURITY_SECRET=$SECURITY_KEY
NEOAVLOD_BOT_ENCRYPTION_KEY=$FERNET_KEY
NEOAVLOD_ADMIN_ORIGIN=https://admin.eduneo.uz
NEOAVLOD_TEACHER_ORIGIN=https://teacher.eduneo.uz
ENV
printf 'Production env yaratildi; secretlar chiqarilmadi.\n'
fi
# Upgrade existing installations without rotating any existing credential.
umask 077
exec 7>"$APP_ROOT/.env-init.lock"
flock -w 60 7
for name in NEOAVLOD_APP_DATABASE_URL NEOAVLOD_ARCHIVE_DATABASE_URL NEOAVLOD_AUDIT_ENCRYPTION_KEY NEOAVLOD_AUDIT_HOST_DIR; do
  if ! grep -q "^$name=.\+" "$FILE"; then
    case "$name" in
      NEOAVLOD_APP_DATABASE_URL) value="postgresql+asyncpg://neoavlod_app:$(openssl rand -hex 32)@database:5432/$(sed -n 's/^POSTGRES_DB=//p' "$FILE" | tail -n 1)" ;;
      NEOAVLOD_ARCHIVE_DATABASE_URL) value="postgresql+asyncpg://neoavlod_archiver:$(openssl rand -hex 32)@database:5432/$(sed -n 's/^POSTGRES_DB=//p' "$FILE" | tail -n 1)" ;;
      NEOAVLOD_AUDIT_ENCRYPTION_KEY) value="$(openssl rand -base64 32 | tr '/+' '_-')" ;;
      NEOAVLOD_AUDIT_HOST_DIR) value="$APP_ROOT/audit-logs" ;;
    esac
    printf '\n%s=%s\n' "$name" "$value" >> "$FILE"
  fi
done
chmod 600 "$FILE"
printf 'Audit environment tayyor; mavjud kalitlar saqlandi.\n'
