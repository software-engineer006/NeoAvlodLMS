#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

SMOKE_DIR="$(mktemp -d /tmp/neoavlod-nginx-smoke.XXXXXX)"
CONTAINER_NAME="neoavlod-nginx-smoke-$RANDOM"
HTTP_PORT="$(( 18080 + RANDOM % 100 ))"
HTTPS_PORT="$(( 18443 + RANDOM % 100 ))"

cleanup() {
  printf 'Tozalanmoqda: %s...\n' "$CONTAINER_NAME"
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  rm -rf "$SMOKE_DIR"
}
trap cleanup EXIT INT TERM

# 1. Mock SSL sertifikatlar yaratish
printf '1. SSL sertifikatlar yaratilmoqda...\n'
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$SMOKE_DIR/privkey.pem" \
  -out "$SMOKE_DIR/fullchain.pem" \
  -subj "/CN=*.eduneo.uz" >/dev/null 2>&1

for sub in eduneo.uz; do
  mkdir -p "$SMOKE_DIR/live/$sub"
  cp "$SMOKE_DIR/privkey.pem" "$SMOKE_DIR/live/$sub/privkey.pem"
  cp "$SMOKE_DIR/fullchain.pem" "$SMOKE_DIR/live/$sub/fullchain.pem"
done

# 2. Frontend dist statik fayllarini tayyorlash
printf '2. Frontend statik fayllari tekshirilmoqda...\n'
mkdir -p "$SMOKE_DIR/www/admin" "$SMOKE_DIR/www/teacher" "$SMOKE_DIR/certbot"
if [[ -d "$AGENT_ROOT/frontend/apps/admin/dist" ]]; then
  cp -r "$AGENT_ROOT/frontend/apps/admin/dist/"* "$SMOKE_DIR/www/admin/"
else
  fail "frontend/apps/admin/dist topilmadi. Avval npm run build bajaring."
fi

if [[ -d "$AGENT_ROOT/frontend/apps/teacher/dist" ]]; then
  cp -r "$AGENT_ROOT/frontend/apps/teacher/dist/"* "$SMOKE_DIR/www/teacher/"
else
  fail "frontend/apps/teacher/dist topilmadi. Avval npm run build bajaring."
fi

# 3. Asl nginx konfiguratsiyasi tekshiruvi (nginx -t)
printf '3. Asl Nginx konfiguratsiyasi tekshirilmoqda (nginx -t)...\n'
docker run --rm \
  -v "$AGENT_ROOT/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$AGENT_ROOT/nginx/conf.d:/etc/nginx/conf.d:ro" \
  -v "$AGENT_ROOT/nginx/snippets:/etc/nginx/snippets:ro" \
  -v "$SMOKE_DIR/live:/etc/letsencrypt/live:ro" \
  -v "$SMOKE_DIR/www/admin:/var/www/neoavlod/admin:ro" \
  -v "$SMOKE_DIR/www/teacher:/var/www/neoavlod/teacher:ro" \
  -v "$SMOKE_DIR/certbot:/var/www/certbot:ro" \
  nginx:1.24-alpine nginx -t

# 4. Docker tarmog‘idagi backend bilan sinov uchun conf moslash
mkdir -p "$SMOKE_DIR/conf.d"
sed 's/server 127.0.0.1:8000;/server backend:8000;/' "$AGENT_ROOT/nginx/conf.d/eduneo.conf" > "$SMOKE_DIR/conf.d/eduneo.conf"

# 5. Nginx test konteynerini ishga tushirish
printf '4. Nginx smoke serveri ishga tushirilmoqda (HTTP=%s, HTTPS=%s)...\n' "$HTTP_PORT" "$HTTPS_PORT"
docker run -d --name "$CONTAINER_NAME" \
  --network "neoavlod-dev_default" \
  -p "127.0.0.1:$HTTP_PORT:80" \
  -p "127.0.0.1:$HTTPS_PORT:443" \
  -v "$AGENT_ROOT/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$SMOKE_DIR/conf.d:/etc/nginx/conf.d:ro" \
  -v "$AGENT_ROOT/nginx/snippets:/etc/nginx/snippets:ro" \
  -v "$SMOKE_DIR/live:/etc/letsencrypt/live:ro" \
  -v "$SMOKE_DIR/www/admin:/var/www/neoavlod/admin:ro" \
  -v "$SMOKE_DIR/www/teacher:/var/www/neoavlod/teacher:ro" \
  -v "$SMOKE_DIR/certbot:/var/www/certbot:ro" \
  nginx:1.24-alpine

sleep 2

# 6. HTTP -> HTTPS 301 Redirect tekshiruvi
printf '5. HTTP -> HTTPS 301 Redirect tekshirilmoqda...\n'
REDIRECT_RESP="$(curl -sI -H "Host: admin.eduneo.uz" "http://127.0.0.1:$HTTP_PORT/groups")"
if [[ "$REDIRECT_RESP" != *"301 Moved Permanently"* || "$REDIRECT_RESP" != *"Location: https://admin.eduneo.uz/groups"* ]]; then
  fail "Admin HTTP -> HTTPS redirect ishlamadi: $REDIRECT_RESP"
fi

REDIRECT_TEACHER="$(curl -sI -H "Host: teacher.eduneo.uz" "http://127.0.0.1:$HTTP_PORT/attendance")"
if [[ "$REDIRECT_TEACHER" != *"301 Moved Permanently"* || "$REDIRECT_TEACHER" != *"Location: https://teacher.eduneo.uz/attendance"* ]]; then
  fail "Teacher HTTP -> HTTPS redirect ishlamadi: $REDIRECT_TEACHER"
fi

REDIRECT_API="$(curl -sI -H "Host: api.eduneo.uz" "http://127.0.0.1:$HTTP_PORT/api/v1/health")"
if [[ "$REDIRECT_API" != *"301 Moved Permanently"* || "$REDIRECT_API" != *"Location: https://api.eduneo.uz/api/v1/health"* ]]; then
  fail "API HTTP -> HTTPS redirect ishlamadi: $REDIRECT_API"
fi
printf 'Redirectlar tasdiqlandi.\n'

# 7. Admin portali SPA va xavfsizlik headerlari tekshiruvi
printf '6. Admin portali SPA fallback va xavfsizlik headerlari tekshirilmoqda...\n'
ADMIN_SPA="$(curl -sk -H "Host: admin.eduneo.uz" "https://127.0.0.1:$HTTPS_PORT/groups")"
if [[ "$ADMIN_SPA" != *'<div id="root">'* ]]; then
  fail "Admin SPA fallback index.html qaytarmadi: $ADMIN_SPA"
fi

ADMIN_HEADERS="$(curl -skI -H "Host: admin.eduneo.uz" "https://127.0.0.1:$HTTPS_PORT/" | tr '[:upper:]' '[:lower:]')"
for header in "x-frame-options: deny" "x-content-type-options: nosniff" "strict-transport-security: max-age=31536000; includesubdomains" "referrer-policy: strict-origin-when-cross-origin"; do
  if [[ "$ADMIN_HEADERS" != *"$header"* ]]; then
    fail "Admin xavfsizlik headeri yetishmaydi: $header"
  fi
done
printf 'Admin SPA va xavfsizlik headerlari tasdiqlandi.\n'

# 8. Teacher portali SPA va headerlar tekshiruvi
printf '7. Teacher portali SPA fallback tekshirilmoqda...\n'
TEACHER_SPA="$(curl -sk -H "Host: teacher.eduneo.uz" "https://127.0.0.1:$HTTPS_PORT/attendance/groups/1")"
if [[ "$TEACHER_SPA" != *'<div id="root">'* ]]; then
  fail "Teacher SPA fallback index.html qaytarmadi: $TEACHER_SPA"
fi
printf 'Teacher SPA tasdiqlandi.\n'

# 9. Statik asset kesh sarlavhasi tekshiruvi
printf '8. Statik asset kesh sarlavhasi tekshirilmoqda...\n'
ASSET_FILE="$(ls "$SMOKE_DIR/www/admin/assets" | head -n 1)"
ASSET_HEADERS="$(curl -skI -H "Host: admin.eduneo.uz" "https://127.0.0.1:$HTTPS_PORT/assets/$ASSET_FILE" | tr '[:upper:]' '[:lower:]')"
if [[ "$ASSET_HEADERS" != *"cache-control: public, max-age=31536000, immutable"* ]]; then
  fail "Statik asset kesh sarlavhasi noto‘g‘ri: $ASSET_HEADERS"
fi
printf 'Statik asset kesh sarlavhasi tasdiqlandi.\n'

# 10. API proksi tekshiruvi (admin, teacher va api.eduneo.uz orqali)
printf '9. Backend API proksi tekshirilmoqda...\n'
ADMIN_API="$(curl -sk -H "Host: admin.eduneo.uz" "https://127.0.0.1:$HTTPS_PORT/api/v1/health")"
if [[ "$ADMIN_API" != *'"status":"ok"'* ]]; then
  fail "admin.eduneo.uz/api/v1/health proksi ishlamadi: $ADMIN_API"
fi

TEACHER_API="$(curl -sk -H "Host: teacher.eduneo.uz" "https://127.0.0.1:$HTTPS_PORT/api/v1/health")"
if [[ "$TEACHER_API" != *'"status":"ok"'* ]]; then
  fail "teacher.eduneo.uz/api/v1/health proksi ishlamadi: $TEACHER_API"
fi

API_SUBDOMAIN="$(curl -sk -H "Host: api.eduneo.uz" "https://127.0.0.1:$HTTPS_PORT/api/v1/health")"
if [[ "$API_SUBDOMAIN" != *'"status":"ok"'* ]]; then
  fail "api.eduneo.uz/api/v1/health proksi ishlamadi: $API_SUBDOMAIN"
fi

API_READY="$(curl -sk -H "Host: api.eduneo.uz" "https://127.0.0.1:$HTTPS_PORT/api/v1/ready")"
if [[ "$API_READY" != *'"status":"ready"'* ]]; then
  fail "api.eduneo.uz/api/v1/ready proksi ishlamadi: $API_READY"
fi
printf 'Backend API barcha subdomenlarda muvaffaqiyatli proksi qilindi.\n'

# 11. Client max body size tekshiruvi (10MB dan katta bo‘lsa 413)
printf '10. Client max body size (10m) chegarasi tekshirilmoqda...\n'
BODY_STATUS="$(curl -sk -o /dev/null -w "%{http_code}" -X POST -H "Host: api.eduneo.uz" -H "Content-Type: application/octet-stream" --data-binary @- "https://127.0.0.1:$HTTPS_PORT/api/v1/health" < <(dd if=/dev/zero bs=1M count=11 2>/dev/null) || true)"
if [[ "$BODY_STATUS" != "413" ]]; then
  fail "10MB dan katta so‘rov 413 qaytarmadi, qaytgan status: $BODY_STATUS"
fi
printf 'Max body size 413 cheklovi tasdiqlandi.\n'

printf 'Barcha Nginx va subdomen smoke tekshiruvlari muvaffaqiyatli o‘tdi!\n'
