#!/usr/bin/env bash
# live 컨테이너 안에서 앱의 관리 명령을 실행한다.
#
#   ./scripts/run.sh <env> migrate status
#   ./scripts/run.sh <env> migrate up --allow-contract
#   ./scripts/run.sh <env> flagctl list
#   ./scripts/run.sh <env> flagctl set show_estimated_delivery on --percent 10
set -euo pipefail
. "$(dirname "$0")/lib.sh"

[ $# -ge 2 ] || die "사용법: run.sh <env> <모듈> [인자...]"
load_env "$1"
MODULE="$2"
shift 2
[ -n "$ACTIVE" ] || die "[$ENV_NAME] 배포된 적이 없다"

compose exec -T "app-$ACTIVE" python -m "app.$MODULE" "$@"
