#!/usr/bin/env bash
# CI의 test 단계와 같은 검사를 로컬에서 돌린다.
#
#   ./scripts/test.sh
#
# 일회용 PostgreSQL 컨테이너를 띄우고, 끝나면 지운다.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
cd "$ROOT"

NAME="cicd-lab-test-db"
PORT=5499

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "$PORT:5432" \
  -e POSTGRES_USER=orders -e POSTGRES_PASSWORD=test -e POSTGRES_DB=orders_test \
  postgres:16-alpine >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT

until docker exec "$NAME" pg_isready -U orders -d orders_test >/dev/null 2>&1; do sleep 0.5; done
# pg_isready가 통과한 직후 초기화 재시작이 한 번 더 일어날 수 있어 잠깐 기다린다.
sleep 1

log "ruff"
ruff check .
log "feature flag 검사"
python3 scripts/check_flags.py
log "pytest"
TEST_DATABASE_URL="postgresql://orders:test@localhost:$PORT/orders_test" REQUIRE_DB=1 pytest -q
