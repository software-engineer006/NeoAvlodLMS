#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PROJECT="neoavlod-smoke-$RANDOM"
SMOKE_DIR="$(mktemp -d /tmp/neoavlod-smoke.XXXXXX)"
ENV_FILE="$SMOKE_DIR/.env.production"

cleanup() {
  printf 'Tozalanmoqda: %s...\n' "$PROJECT"
  docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$SMOKE_DIR"
}
trap cleanup EXIT INT TERM

# 1. Disposable secrets yaratish
DB_PASS="$(openssl rand -hex 16)"
SEC_SECRET="$(openssl rand -hex 32)"
FERNET_KEY="$(openssl rand -base64 32 | tr '/+' '_-')"
FREE_PORT="$(( 19000 + RANDOM % 1000 ))"

cat <<EOF > "$ENV_FILE"
POSTGRES_USER=neoavlod_smoke
POSTGRES_DB=neoavlod_smoke
POSTGRES_PASSWORD=$DB_PASS
API_PORT=$FREE_PORT
NEOAVLOD_ENVIRONMENT=production
NEOAVLOD_DEBUG=false
NEOAVLOD_DATABASE_URL=postgresql+asyncpg://neoavlod_smoke:$DB_PASS@database:5432/neoavlod_smoke
NEOAVLOD_SECURITY_SECRET=$SEC_SECRET
NEOAVLOD_BOT_ENCRYPTION_KEY=$FERNET_KEY
NEOAVLOD_ADMIN_ORIGIN=https://admin.eduneo.uz
NEOAVLOD_TEACHER_ORIGIN=https://teacher.eduneo.uz
EOF

chmod 600 "$ENV_FILE"

printf '1. Production Docker imagelari qurilmoqda...\n'
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" build

printf '2. Nonroot user (UID 1000) tekshirilmoqda...\n'
IMAGE_UID="$(docker run --rm neoavlod-backend:production id -u)"
IMAGE_USER="$(docker run --rm neoavlod-backend:production whoami)"
if [[ "$IMAGE_UID" != "1000" || "$IMAGE_USER" != "app" ]]; then
  fail "Production image nonroot user talabiga mos kelmadi: UID=$IMAGE_UID USER=$IMAGE_USER"
fi
printf 'Nonroot tasdiqlandi: UID=%s USER=%s\n' "$IMAGE_UID" "$IMAGE_USER"

printf '3. Disposable production stack ishga tushirilmoqda...\n'
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" up -d --wait

printf '4. Worker singleton tekshirilmoqda...\n'
WORKER_COUNT="$(docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" ps -q worker | wc -l | tr -d ' ')"
if [[ "$WORKER_COUNT" != "1" ]]; then
  fail "Worker singleton talabi buzildi, replikalar soni: $WORKER_COUNT"
fi
printf 'Worker singleton tasdiqlandi (count=%s)\n' "$WORKER_COUNT"

printf '5. Worker --once test qilinmoqda...\n'
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" run --rm worker python -m neoavlod.cli worker --once

printf '6. Production API health va ready tekshirilmoqda (port %s)...\n' "$FREE_PORT"
for i in {1..15}; do
  if curl -sf "http://127.0.0.1:$FREE_PORT/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

HEALTH_RESP="$(curl -sf "http://127.0.0.1:$FREE_PORT/api/v1/health")"
printf 'Health response: %s\n' "$HEALTH_RESP"
if [[ "$HEALTH_RESP" != *'"status":"ok"'* ]]; then
  fail "Health tekshiruvi kutilgan javobni qaytarmadi: $HEALTH_RESP"
fi

READY_RESP="$(curl -sf "http://127.0.0.1:$FREE_PORT/api/v1/ready")"
printf 'Ready response: %s\n' "$READY_RESP"
if [[ "$READY_RESP" != *'"status":"ready"'* ]]; then
  fail "Ready tekshiruvi kutilgan javobni qaytarmadi: $READY_RESP"
fi

printf 'Barcha production Docker tekshiruvlari muvaffaqiyatli o‘tdi.\n'
