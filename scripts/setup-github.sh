#!/usr/bin/env bash
# GitHub 리포의 Environments를 촬영용으로 준비한다 (gh CLI 필요).
#
#   ./scripts/setup-github.sh
#
# 하는 일:
#   - staging, production environment 생성
#   - production에 Required reviewers(본인) 설정
#   - 두 environment에 서로 다른 DB_PASSWORD secret 등록
#
# 화면에서 직접 하려면: Settings → Environments.
set -euo pipefail
. "$(dirname "$0")/lib.sh"

REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
USER_ID="$(gh api user --jq .id)"

log "$REPO: staging environment"
gh api --silent -X PUT "repos/$REPO/environments/staging"

log "$REPO: production environment (승인자: $(gh api user --jq .login))"
gh api --silent -X PUT "repos/$REPO/environments/production" --input - <<JSON
{"reviewers": [{"type": "User", "id": $USER_ID}]}
JSON

for NAME in staging production; do
  log "$NAME: DB_PASSWORD secret"
  gh secret set DB_PASSWORD --repo "$REPO" --env "$NAME" --body "$(openssl rand -hex 16)"
done

ok "완료. https://github.com/$REPO/settings/environments 에서 확인한다."
