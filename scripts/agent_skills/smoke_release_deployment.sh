#!/usr/bin/env bash
# Exercise the real release scripts against disposable PostgreSQL/API/worker and TLS Nginx.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
TEST_DIR="$(mktemp -d /tmp/neoavlod-live-release.XXXXXX)"
PROJECT="neoavlod-release-smoke-$RANDOM"
NGINX_NAME="$PROJECT-nginx"
A="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
B="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
C="cccccccccccccccccccccccccccccccccccccccc"
export APP_ROOT="$TEST_DIR/app" WEB_ROOT="$TEST_DIR/web" BACKUP_ROOT="$TEST_DIR/backups"
export NGINX_CONFIG_ROOT="$TEST_DIR/nginx" COMPOSE_PROJECT_NAME="$PROJECT"
export PORTAL_HTTPS_PORT=443 PORTAL_CA_FILE="$TEST_DIR/cert/fullchain.pem"
mkdir -p "$APP_ROOT/releases" "$WEB_ROOT/releases" "$BACKUP_ROOT" "$NGINX_CONFIG_ROOT/conf.d" "$NGINX_CONFIG_ROOT/snippets" "$TEST_DIR/bin" "$TEST_DIR/cert/live/eduneo.uz"
cleanup() {
  docker rm -f "$NGINX_NAME" >/dev/null 2>&1 || true
  if [[ -f "$APP_ROOT/releases/$A/compose.prod.yaml" ]]; then
    NEOAVLOD_RELEASE_ID="$A" docker compose -p "$PROJECT" --env-file "$APP_ROOT/.env.production" -f "$APP_ROOT/releases/$A/compose.prod.yaml" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  # The Linux runner creates root-owned release/state directories. Restore the
  # invoking user's ownership before host cleanup (GitHub runners are nonroot).
  if docker image inspect neoavlod-release-smoke-runner >/dev/null 2>&1; then
    docker run --rm --user 0:0 -v "$TEST_DIR:/cleanup" \
      neoavlod-release-smoke-runner sh -c 'chown -R "$1:$2" /cleanup' \
      sh "$(id -u)" "$(id -g)"
  fi
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT
# Docker builds use the working tree to include the changes under review, never production data.
for release in "$A" "$B" "$C"; do
  mkdir -p "$APP_ROOT/releases/$release"
  tar -C "$AGENT_ROOT" --exclude='node_modules' --exclude='dist' --exclude='*.tsbuildinfo' --exclude='__pycache__' \
    -cf - backend/src backend/alembic backend/alembic.ini backend/pyproject.toml backend/Dockerfile \
    compose.prod.yaml .dockerignore scripts/deploy nginx frontend | tar -xf - -C "$APP_ROOT/releases/$release"
  sed -i.bak 's/server 127.0.0.1:8000;/server api:8000;/' "$APP_ROOT/releases/$release/nginx/conf.d/eduneo.conf"
  rm "$APP_ROOT/releases/$release/nginx/conf.d/eduneo.conf.bak"
done
bash "$AGENT_ROOT/scripts/deploy/init_production_env.sh"
# Private import is exercised with synthetic CSVs only, never the user's rosters.
docker run --rm -i --user "$(id -u):$(id -g)" \
  -v "$AGENT_ROOT:/workspace:ro" -v "$TEST_DIR:$TEST_DIR" -e APP_ROOT \
  neoavlod-backend:development python - <<'PY'
import argparse, asyncio, csv, json, os
from pathlib import Path
from neoavlod.educenter_import import FILES, LESSONS, run
root = Path(os.environ['APP_ROOT']) / 'private/educenter_data'
root.mkdir(parents=True)
for index, filename in enumerate(FILES):
    header = ['Mygov', 'Maktab', '', 'Ism', 'Raqam', 'Sinf'] + [''] * 9
    for col, day in LESSONS[index].items():
        header[col] = str(int(day[-2:]))
    if index == 2:
        header[6] = '23'
    one = ['', '', '1', f'Synthetic {index} A', '', '7-sinf'] + [''] * 9
    two = ['', '', '2', f'Synthetic {index} B', '', ''] + [''] * 9
    for col in LESSONS[index]:
        one[col] = 'k'
    with (root / filename).open('w', newline='') as f:
        csv.writer(f, delimiter=';').writerows([header, one, two])
profiles = [
    {'username': 'ceo_mohira', 'first_name': 'Synthetic Owner', 'role': 'superadmin'},
    {'username': 'teacher_jasurbek', 'first_name': 'Synthetic Teacher A', 'role': 'teacher'},
    {'username': 'teacher_dilmurod', 'first_name': 'Synthetic Teacher B', 'role': 'teacher'},
]
(root / 'staff-profiles.json').write_text(json.dumps(profiles))
report = root.parent / 'reviewed.json'
asyncio.run(run(argparse.Namespace(source=root, year=2026, capacity=30, report=report,
                                  credentials=root.parent / 'unused.json', apply=False)))
(root / 'plan.sha256').write_text(json.loads(report.read_text())['plan_sha256'])
PY
printf '\nAPI_PORT=%s\n' "$((25000 + RANDOM % 1000))" >> "$APP_ROOT/.env.production"
cp "$AGENT_ROOT/nginx/acme-http.conf" "$NGINX_CONFIG_ROOT/conf.d/neoavlod-acme.conf"
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
  -keyout "$TEST_DIR/cert/live/eduneo.uz/privkey.pem" -out "$PORTAL_CA_FILE" \
  -subj '/CN=eduneo.uz' -addext 'subjectAltName=DNS:admin.eduneo.uz,DNS:teacher.eduneo.uz,DNS:api.eduneo.uz' >/dev/null 2>&1
cp "$PORTAL_CA_FILE" "$TEST_DIR/cert/live/eduneo.uz/fullchain.pem"
NEOAVLOD_RELEASE_ID="$A" docker compose -p "$PROJECT" --env-file "$APP_ROOT/.env.production" -f "$APP_ROOT/releases/$A/compose.prod.yaml" up -d --wait database
# Nginx and systemd wrappers only bridge to the real TLS Nginx container.
cat > "$TEST_DIR/bin/nginx" <<WRAPPER
#!/bin/sh
exec docker exec "$NGINX_NAME" nginx "\$@"
WRAPPER
cat > "$TEST_DIR/bin/systemctl" <<WRAPPER
#!/bin/sh
exec docker exec "$NGINX_NAME" nginx -s reload
WRAPPER
chmod +x "$TEST_DIR/bin/"*
export PATH="$TEST_DIR/bin:$PATH"
export AGENT_ROOT
docker run -d --name "$NGINX_NAME" --network "${PROJECT}_default" \
  -v "$AGENT_ROOT/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$NGINX_CONFIG_ROOT/conf.d:/etc/nginx/conf.d:ro" \
  -v "$NGINX_CONFIG_ROOT/snippets:/etc/nginx/snippets:ro" \
  -v "$TEST_DIR/cert/live:/etc/letsencrypt/live:ro" \
  -v "$WEB_ROOT:/var/www/neoavlod:ro" nginx:1.24-alpine >/dev/null
# Force proxy probes to use direct loopback even on machines with corporate proxy variables.
docker build -t neoavlod-release-smoke-runner -f "$AGENT_ROOT/scripts/agent_skills/Dockerfile.release-smoke" "$AGENT_ROOT"
docker run --rm --network "container:$NGINX_NAME" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$AGENT_ROOT:$AGENT_ROOT:ro" -v "$TEST_DIR:$TEST_DIR" \
  -e AGENT_ROOT -e APP_ROOT -e WEB_ROOT -e BACKUP_ROOT -e NGINX_CONFIG_ROOT \
  -e COMPOSE_PROJECT_NAME -e PORTAL_HTTPS_PORT -e PORTAL_CA_FILE \
  -e "PATH=$TEST_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  -i neoavlod-release-smoke-runner bash -s <<'LINUX_TEST'
set -euo pipefail
A=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
B=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
C=cccccccccccccccccccccccccccccccccccccccc
TEST_DIR="$(dirname "$APP_ROOT")"
fail() { echo "$*" >&2; exit 1; }
bash "$AGENT_ROOT/scripts/deploy/deploy.sh" "$A" </dev/null
bash "$AGENT_ROOT/scripts/deploy/deploy.sh" "$B" </dev/null
# Both releases import the same source; counts must stay unchanged after rerun.
bash "$AGENT_ROOT/scripts/deploy/appctl.sh" exec -T api python - <<'PY'
import asyncio
from sqlalchemy import func, select
from neoavlod.database import Database
from neoavlod.settings import Settings
from neoavlod.models import Staff, Group, Student, Attendance, AttendanceBatch, NotificationOutbox
async def verify():
    db = Database(Settings())
    try:
        async with db.session() as s:
            for model, expected in ((Staff, 3), (Group, 4), (Student, 8), (Attendance, 44),
                                    (AttendanceBatch, 22), (NotificationOutbox, 0)):
                assert await s.scalar(select(func.count()).select_from(model)) == expected
    finally:
        await db.close()
asyncio.run(verify())
print('OK: production Docker private import and unchanged second release counts.')
PY
[[ "$(docker inspect --format '{{.Config.Image}}' "$(NEOAVLOD_RELEASE_ID="$B" docker compose -p "$COMPOSE_PROJECT_NAME" --env-file "$APP_ROOT/.env.production" -f "$APP_ROOT/releases/$B/compose.prod.yaml" ps -q api)")" == "neoavlod-backend:$B" ]]
# Invalid TLS configuration after runtime replacement must restore old image + both frontends.
printf '\ninvalid_neoavlod_directive on;\n' >> "$APP_ROOT/releases/$C/nginx/conf.d/eduneo.conf"
if bash "$AGENT_ROOT/scripts/deploy/deploy.sh" "$C" </dev/null > "$TEST_DIR/failed.log" 2>&1; then fail 'Buzuq Nginx deploy qabul qilindi.'; fi
[[ "$(basename "$(readlink "$APP_ROOT/current")")" == "$B" ]]
[[ "$(basename "$(readlink "$WEB_ROOT/current")")" == "$B" ]]
[[ ! -f "$APP_ROOT/releases/$C/.successful" ]]
bash "$AGENT_ROOT/scripts/deploy/rollback.sh" </dev/null
[[ "$(basename "$(readlink "$APP_ROOT/current")")" == "$A" ]]
[[ "$(basename "$(readlink "$WEB_ROOT/current")")" == "$A" ]]
IMAGE="$(bash "$AGENT_ROOT/scripts/deploy/appctl.sh" ps -q api)"
[[ "$(docker inspect --format '{{.Config.Image}}' "$IMAGE")" == "neoavlod-backend:$A" ]]
BACKUP="$(find "$BACKUP_ROOT" -name '*.dump' -print -quit)"
bash "$AGENT_ROOT/scripts/deploy/appctl.sh" exec -T database pg_restore --list < "$BACKUP" >/dev/null
printf 'OK: real versioned backend + 2 static portals, backup/migrations, automatic and manual rollback, valid TLS probes.\n'
touch "$TEST_DIR/passed"
LINUX_TEST
[[ -f "$TEST_DIR/passed" ]] || fail 'Deployment smoke oxirigacha bajarilmadi.'
