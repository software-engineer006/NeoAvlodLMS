#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/neoavlod}"
FILE="$APP_ROOT/.env.production"
mkdir -p "$APP_ROOT"
[[ ! -e "$FILE" ]] || { echo 'Mavjud production env saqlandi.'; exit 0; }
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
