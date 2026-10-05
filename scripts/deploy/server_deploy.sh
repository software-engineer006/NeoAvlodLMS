#!/usr/bin/env bash
# Root server: fetch the exact tested main commit, archive immutable source and deploy.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
REPO_ROOT="${REPO_ROOT:-/root/NeoAvlodLMS}"
RELEASE_ID="${1:?Usage: server_deploy.sh <full_git_sha>}"
valid_release "$RELEASE_ID"
mkdir -p "$APP_ROOT/releases"
exec 8>"$APP_ROOT/.source.lock"
flock -w 600 8 || fail 'Boshqa server deploy tugamadi.'
git -C "$REPO_ROOT" fetch --prune origin main
[[ "$(git -C "$REPO_ROOT" rev-parse origin/main)" == "$RELEASE_ID" ]] || fail 'Commit main dagi joriy SHA emas; eski pipeline deploy qilinmaydi.'
STAGE="$(mktemp -d "$APP_ROOT/releases/.stage.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
git -C "$REPO_ROOT" archive "$RELEASE_ID" | tar -x -C "$STAGE"
if [[ ! -d "$APP_ROOT/releases/$RELEASE_ID" ]]; then
  mv "$STAGE" "$APP_ROOT/releases/$RELEASE_ID"
fi
bash "$APP_ROOT/releases/$RELEASE_ID/scripts/deploy/deploy.sh" "$RELEASE_ID" </dev/null
