#!/usr/bin/env bash
# 배포 직후 "살아 있고, 핵심 흐름이 한 번은 된다"만 확인한다.
#
#   ./scripts/smoke_test.sh http://localhost:9080
set -euo pipefail

BASE_URL="${1:?사용법: smoke_test.sh <base-url>}"

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf '  ✔ %s\n' "$name"
  else
    printf '  ✘ %s\n' "$name" >&2
    exit 1
  fi
}

request() { curl --silent --show-error --fail --max-time 5 "$@"; }

check "healthz" request "$BASE_URL/healthz"
check "readyz (DB 연결)" request "$BASE_URL/readyz"

# 주문을 하나 만들고 주문 완료 화면까지 열어 본다.
ORDER_JSON="$(request -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"smoke-test","book_title":"smoke test","quantity":1}')" \
  || { echo "  ✘ 주문 생성" >&2; exit 1; }
ORDER_ID="$(printf '%s' "$ORDER_JSON" | sed -E 's/.*"id":[[:space:]]*([0-9]+).*/\1/')"
printf '  ✔ 주문 생성 (#%s)\n' "$ORDER_ID"

check "주문 조회" request "$BASE_URL/orders/$ORDER_ID"
check "주문 완료 화면" request "$BASE_URL/orders/$ORDER_ID/complete"

VERSION="$(request "$BASE_URL/info" | sed -E 's/.*"version":[[:space:]]*"([^"]+)".*/\1/')"
printf '  smoke test 통과 (version=%s)\n' "$VERSION"
