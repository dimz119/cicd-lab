#!/usr/bin/env bash
# 환경을 통째로 지운다 (컨테이너, DB 볼륨, 배포 상태).
#
#   ./scripts/teardown.sh <env>
#   ./scripts/teardown.sh all
set -euo pipefail
. "$(dirname "$0")/lib.sh"

[ $# -eq 1 ] || die "사용법: teardown.sh <env|all>"

if [ "$1" = "all" ]; then
  TARGETS="dev staging production"
else
  TARGETS="$1"
fi

for NAME in $TARGETS; do
  load_env "$NAME" 2>/dev/null
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$STATE_DIR"
  ok "[$NAME] 정리 완료"
done
