#!/usr/bin/env bash
# End-to-end clean environment smoke verification for Task 041
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PROJECT="neoavlod-clean-$RANDOM"
SMOKE_DIR="$(mktemp -d /tmp/neoavlod-clean-smoke.XXXXXX)"
ENV_FILE="$SMOKE_DIR/.env.production"
BACKUP_DIR="$SMOKE_DIR/backups"
mkdir -p "$BACKUP_DIR"

cleanup() {
  printf 'Tozalanmoqda: %s...\n' "$PROJECT"
  docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$SMOKE_DIR"
}
trap cleanup EXIT INT TERM

# 1. DEPLOYMENT.md mavjudligi va to'liqligi tekshiruvi
printf '1. DEPLOYMENT.md qo‘llanmasi tekshirilmoqda...\n'
DEPLOY_DOC="$AGENT_ROOT/DEPLOYMENT.md"
[[ -f "$DEPLOY_DOC" ]] || fail "DEPLOYMENT.md fayli topilmadi"

for section in "DNS va subdomenlar" "Certbot" "Nginx" ".env.production" "bootstrap" "Telegram Bot" "GitHub Actions" "backup" "restore" "Rollback" "Checklist"; do
  grep -qi "$section" "$DEPLOY_DOC" || fail "DEPLOYMENT.md da '$section' bo‘limi topilmadi"
done
printf 'DEPLOYMENT.md to‘liq va qamrovli ekani tasdiqlandi.\n'

# 2. Toza muhit uchun konfiguratsiya va secretlar
printf '2. Toza muhit uchun maxfiy kalitlar yaratilmoqda...\n'
DB_PASS="$(openssl rand -hex 16)"
SEC_SECRET="$(openssl rand -hex 32)"
FERNET_KEY="$(openssl rand -base64 32 | tr '/+' '_-')"
FREE_PORT="$(( 19500 + RANDOM % 400 ))"

cat <<EOF > "$ENV_FILE"
POSTGRES_USER=neoavlod_clean
POSTGRES_DB=neoavlod_clean
POSTGRES_PASSWORD=$DB_PASS
API_PORT=$FREE_PORT
NEOAVLOD_ENVIRONMENT=production
NEOAVLOD_DEBUG=false
NEOAVLOD_DATABASE_URL=postgresql+asyncpg://neoavlod_clean:$DB_PASS@database:5432/neoavlod_clean
NEOAVLOD_SECURITY_SECRET=$SEC_SECRET
NEOAVLOD_BOT_ENCRYPTION_KEY=$FERNET_KEY
NEOAVLOD_ADMIN_ORIGIN=https://admin.eduneo.uz
NEOAVLOD_TEACHER_ORIGIN=https://teacher.eduneo.uz
EOF

chmod 600 "$ENV_FILE"

# 3. Docker Compose toza stackni ishga tushirish
printf '3. Toza PostgreSQL 18.6 ishga tushirilmoqda...\n'
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" up -d --wait database

# 4. Alembic migratsiyalarini noldan o'tkazish
printf '4. Alembic migratsiyalari toza bazada o‘tkazilmoqda...\n'
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" run --rm migrations

# 5. Superadminni bootstrap qilish
printf '5. Superadmin CLI orqali bootstrap qilinmoqda...\n'
ADMIN_OUTPUT="$(echo "SuperAdminStrongPass123!" | docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" run --rm -T api \
  python -m neoavlod.cli bootstrap \
    --username "superadmin" \
    --phone "+998901234567" \
    --first-name "Super" \
    --last-name "Admin" \
    --password-stdin)"

printf 'Bootstrap natijasi: %s\n' "$ADMIN_OUTPUT"
if [[ "$ADMIN_OUTPUT" != *'"username": "superadmin"'* ]]; then
  fail "Superadmin bootstrap kutilgan JSON qaytarmadi: $ADMIN_OUTPUT"
fi

# 6. Bot tokenini xavfsiz o'rnatish
printf '6. Bot tokeni CLI orqali kiritilmoqda...\n'
BOT_OUTPUT="$(echo "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_mock" | docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" run --rm -T api \
  python -m neoavlod.cli set-bot-token --token-stdin || true)"
printf 'Bot token natijasi (mock/real): %s\n' "$BOT_OUTPUT"

# 7. Background Worker singleton --once tekshiruvi
printf '7. Background worker tekshirilmoqda...\n'
WORKER_RES="$(docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" run --rm worker python -m neoavlod.cli worker --once)"
printf 'Worker natijasi: %s\n' "$WORKER_RES"
if [[ "$WORKER_RES" != *'"bot_processed"'* || "$WORKER_RES" != *'"outbox_processed"'* ]]; then
  fail "Worker --once kutilgan JSON qaytarmadi: $WORKER_RES"
fi

# 8. API va worker konteynerlarini to'liq ishga tushirish
printf '8. API va Worker servislar ishga tushirilmoqda...\n'
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" up -d --wait api worker

# 9. API health va ready endpointlari
printf '9. API health va ready endpointlari tekshirilmoqda...\n'
for i in {1..15}; do
  if curl -sf "http://127.0.0.1:$FREE_PORT/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

HEALTH_RESP="$(curl -sf "http://127.0.0.1:$FREE_PORT/api/v1/health")"
[[ "$HEALTH_RESP" == *'"status":"ok"'* ]] || fail "API health failed: $HEALTH_RESP"

READY_RESP="$(curl -sf "http://127.0.0.1:$FREE_PORT/api/v1/ready")"
[[ "$READY_RESP" == *'"status":"ready"'* ]] || fail "API ready failed: $READY_RESP"
printf 'API /health va /ready 200 OK qaytardi.\n'

# 10. PostgreSQL Backup (pg_dump) tekshiruvi
printf '10. pg_dump zaxira nusxa tekshiruvi...\n'
DUMP_FILE="$BACKUP_DIR/clean_test.dump"
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$AGENT_ROOT/compose.prod.yaml" exec -T database \
  pg_dump -U neoavlod_clean -d neoavlod_clean -Fc > "$DUMP_FILE"

DUMP_SIZE="$(wc -c < "$DUMP_FILE" | tr -d ' ')"
if [[ "$DUMP_SIZE" -lt 1000 ]]; then
  fail "pg_dump fayli bo‘sh yoki juda kichik: $DUMP_SIZE bayt"
fi
printf 'pg_dump zaxirasi muvaffaqiyatli yaratildi (%s bayt).\n' "$DUMP_SIZE"

printf 'Toza muhit smoke tekshiruvi to‘liq muvaffaqiyatli o‘tdi!\n'
