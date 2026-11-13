#!/usr/bin/env bash
# 환경의 앱 로그를 본다.
#
#   ./scripts/logs.sh <env>          최근 로그
#   ./scripts/logs.sh <env> -f       계속 따라가기
set -euo pipefail
. "$(dirname "$0")/lib.sh"

[ $# -ge 1 ] || die "사용법: logs.sh <env> [-f]"
load_env "$1"
shift

compose logs --no-log-prefix --tail 20 "$@" app-blue app-green
