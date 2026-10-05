#!/usr/bin/env bash
# Remote deployment via SSH with pinned host
set -euo pipefail

SSH_USER="${SSH_USER:?SSH_USER must be set}"
SSH_HOST="${SSH_HOST:?SSH_HOST must be set}"
SSH_PORT="${SSH_PORT:-22}"
RELEASE_ID="${RELEASE_ID:-$(git rev-parse --short HEAD)}"

printf '==> Serverga masofaviy deployment: %s@%s:%s (Release: %s)...\n' "$SSH_USER" "$SSH_HOST" "$SSH_PORT" "$RELEASE_ID"

SSH_CMD="ssh -p $SSH_PORT -o StrictHostKeyChecking=yes -o BatchMode=yes"
SCP_CMD="scp -P $SSH_PORT -o StrictHostKeyChecking=yes -o BatchMode=yes"

# 1. SSH ulanishini tekshirish
printf '==> Pinned SSH host ulanishi tekshirilmoqda...\n'
$SSH_CMD "$SSH_USER@$SSH_HOST" "echo 'SSH ulanishi muvaffaqiyatli'"

# 2. Release arxivini tayyorlash
TMP_TAR="$(mktemp /tmp/neoavlod-release.XXXXXX.tar.gz)"
printf '==> Release arxivi yaratilmoqda: %s...\n' "$TMP_TAR"

tar -czf "$TMP_TAR" \
  -C "${DIST_DIR:-dist}" . \
  scripts/deploy/deploy.sh \
  scripts/deploy/rollback.sh \
  compose.prod.yaml \
  nginx/

# 3. Serverga yuklash
printf '==> Arxiv serverga nusxalanmoqda...\n'
$SCP_CMD "$TMP_TAR" "$SSH_USER@$SSH_HOST:/tmp/release-$RELEASE_ID.tar.gz"
rm -f "$TMP_TAR"

# 4. Serverda ochish va deploy.sh ni ishga tushirish
printf '==> Serverda deployment bajarilmoqda...\n'
$SSH_CMD "$SSH_USER@$SSH_HOST" "bash -s" <<EOF
set -euo pipefail
mkdir -p /tmp/release-$RELEASE_ID
tar -xzf /tmp/release-$RELEASE_ID.tar.gz -C /tmp/release-$RELEASE_ID
rm -f /tmp/release-$RELEASE_ID.tar.gz

chmod +x /tmp/release-$RELEASE_ID/scripts/deploy/*.sh
sudo /tmp/release-$RELEASE_ID/scripts/deploy/deploy.sh "$RELEASE_ID" /tmp/release-$RELEASE_ID

rm -rf /tmp/release-$RELEASE_ID
EOF

printf '==> Masofaviy deployment muvaffaqiyatli yakunlandi!\n'
