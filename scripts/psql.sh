#!/usr/bin/env bash
# 환경의 DB에 psql로 붙는다.
#
#   ./scripts/psql.sh <env>                    대화형
#   ./scripts/psql.sh <env> -c '\d orders'     명령 한 번
set -euo pipefail
. "$(dirname "$0")/lib.sh"

[ $# -ge 1 ] || die "사용법: psql.sh <env> [psql 인자...]"
load_env "$1"
shift

if [ -t 0 ]; then
  compose exec db psql -U orders -d orders "$@"
else
  compose exec -T db psql -U orders -d orders "$@"
fi
