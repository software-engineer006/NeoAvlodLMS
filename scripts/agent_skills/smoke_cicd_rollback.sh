#!/usr/bin/env bash
# Smoke test verifying GitHub Actions CI/CD workflow and atomic deploy/rollback logic
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

TEST_DIR="$(mktemp -d /tmp/neoavlod-deploy-test.XXXXXX)"
WEB_DIR="$TEST_DIR/web"
APP_DIR="$TEST_DIR/app"

cleanup() {
  printf 'Tozalanmoqda: %s...\n' "$TEST_DIR"
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT INT TERM

# 1. GitHub Actions workflow tekshiruvi
printf '1. GitHub Actions CI/CD workflow tekshirilmoqda...\n'
WORKFLOW_FILE="$AGENT_ROOT/.github/workflows/ci-cd.yaml"
[[ -f "$WORKFLOW_FILE" ]] || fail ".github/workflows/ci-cd.yaml fayli topilmadi"

# YAML sintaksisini tekshirish (Python orqali Dockerda)
./scripts/agent_skills/docker_env.sh exec python -c "
import yaml
with open('/workspace/.github/workflows/ci-cd.yaml') as f:
    data = yaml.safe_load(f)
assert 'jobs' in data
assert 'test' in data['jobs']
assert 'deploy' in data['jobs']
assert 'rollback' in data['jobs']
assert data['jobs']['test']['services']['postgres']['image'] == 'postgres:18.6'
print('Workflow YAML sintaksisi va struktura tasdiqlandi.')
"

# Pinned SSH va muhim qadamlarni tekshirish
grep -q "known_hosts" "$WORKFLOW_FILE" || fail "Workflowda pinned SSH known_hosts topilmadi"
grep -q "StrictHostKeyChecking=yes" "$WORKFLOW_FILE" || fail "Workflowda StrictHostKeyChecking=yes topilmadi"
grep -q "npm ci" "$WORKFLOW_FILE" || fail "Workflowda npm ci topilmadi"
grep -q "npm run build" "$WORKFLOW_FILE" || fail "Workflowda npm run build topilmadi"
grep -q "alembic upgrade head" "$WORKFLOW_FILE" || fail "Workflowda alembic upgrade head topilmadi"

printf 'CI/CD workflow spetsifikatsiyasi to‘liq tasdiqlandi.\n'

# 2. Deploy va Rollback skriptlarini simulyatsiya qilish
printf '2. Atomik deployment (Release 1) sinovdan o‘tkazilmoqda...\n'
mkdir -p "$WEB_DIR" "$APP_DIR"

export WEB_ROOT="$WEB_DIR"
export APP_ROOT="$APP_DIR"
export SKIP_RELOAD_NGINX="1"
export SKIP_DOCKER="1"
export HEALTH_CHECK_URL="http://127.0.0.1:8000/api/v1/health"
export READY_CHECK_URL="http://127.0.0.1:8000/api/v1/ready"

"$AGENT_ROOT/scripts/deploy/deploy.sh" "release-001" "$AGENT_ROOT/frontend/apps"

# Tekshirish: current -> releases/release-001
CURRENT_TARGET="$(readlink "$WEB_DIR/current")"
[[ "$CURRENT_TARGET" == "releases/release-001" ]] || fail "Current symlink noto‘g‘ri: $CURRENT_TARGET"
[[ -f "$WEB_DIR/admin/index.html" ]] || fail "Admin index.html topilmadi"
[[ -f "$WEB_DIR/teacher/index.html" ]] || fail "Teacher index.html topilmadi"
printf 'Release 1 muvaffaqiyatli o‘rnatildi.\n'

# 3. Ikkinchi release deployment
printf '3. Ikkinchi atomik deployment (Release 2) sinovdan o‘tkazilmoqda...\n'
"$AGENT_ROOT/scripts/deploy/deploy.sh" "release-002" "$AGENT_ROOT/frontend/apps"

CURRENT_TARGET="$(readlink "$WEB_DIR/current")"
[[ "$CURRENT_TARGET" == "releases/release-002" ]] || fail "Current symlink noto‘g‘ri: $CURRENT_TARGET"
PREV_STORED="$(cat "$APP_DIR/.previous_release" | tr -d '[:space:]')"
[[ "$PREV_STORED" == "release-001" ]] || fail "Oldingi release noto‘g‘ri saqlangan: $PREV_STORED"
printf 'Release 2 muvaffaqiyatli o‘rnatildi (Previous: %s).\n' "$PREV_STORED"

# 4. Muvaffaqiyatsiz deployda avtomatik ROLLBACK sinovi
printf '4. Muvaffaqiyatsiz deploymentda avtomatik ROLLBACK tekshirilmoqda...\n'
set +e
HEALTH_CHECK_URL="http://127.0.0.1:59999/unreachable" \
"$AGENT_ROOT/scripts/deploy/deploy.sh" "release-003-broken" "$AGENT_ROOT/frontend/apps" > "$TEST_DIR/deploy_fail.log" 2>&1
DEPLOY_CODE=$?
set -e

if [[ "$DEPLOY_CODE" -eq 0 ]]; then
  fail "Buzuq health checkli deploy xato bermadi!"
fi

# Avtomatik rollback ishlaganini tekshirish: current yana release-002 bo'lishi kerak!
CURRENT_TARGET="$(readlink "$WEB_DIR/current")"
if [[ "$CURRENT_TARGET" != "releases/release-002" ]]; then
  fail "Avtomatik rollback ishlamadi! Hozirgi target: $CURRENT_TARGET (kutilgan: releases/release-002)"
fi
printf 'Avtomatik rollback muvaffaqiyatli ishladi (reverted to %s).\n' "$CURRENT_TARGET"

# 5. Qo'lda (Manual) ROLLBACK sinovi
printf '5. Qo‘lda rollback.sh chaqirilishi tekshirilmoqda...\n'
HEALTH_CHECK_URL="http://127.0.0.1:8000/api/v1/health" \
"$AGENT_ROOT/scripts/deploy/rollback.sh"

CURRENT_TARGET="$(readlink "$WEB_DIR/current")"
if [[ "$CURRENT_TARGET" != "releases/release-001" ]]; then
  fail "Qo‘lda rollback ishlamadi! Hozirgi target: $CURRENT_TARGET (kutilgan: releases/release-001)"
fi
printf 'Qo‘lda rollback muvaffaqiyatli ishladi (reverted to %s).\n' "$CURRENT_TARGET"

# 6. Eski releaselarni avtomatik tozalash (pruning) tekshiruvi
printf '6. Eski releaselar tozalanishi (retention limit 5) tekshirilmoqda...\n'
for num in 010 011 012 013 014 015 016; do
  "$AGENT_ROOT/scripts/deploy/deploy.sh" "release-$num" "$AGENT_ROOT/frontend/apps" >/dev/null 2>&1
done

RELEASES_COUNT="$(ls -1 "$WEB_DIR/releases" | wc -l | tr -d ' ')"
if [[ "$RELEASES_COUNT" -gt 5 ]]; then
  fail "Releaselar soni 5 tadan oshib ketdi: $RELEASES_COUNT"
fi
printf 'Retention pruning tasdiqlandi (saqlangan releaselar soni: %s).\n' "$RELEASES_COUNT"

printf 'Barcha CI/CD va Rollback tekshiruvlari muvaffaqiyatli o‘tdi!\n'
