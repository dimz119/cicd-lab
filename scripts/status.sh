#!/usr/bin/env bash
# 환경의 현재 배포 상태를 보여 준다.
#
#   ./scripts/status.sh <env>
set -euo pipefail
. "$(dirname "$0")/lib.sh"

[ $# -eq 1 ] || die "사용법: status.sh <env>"
load_env "$1" 2>/dev/null

if [ -z "$ACTIVE" ]; then
  echo "[$ENV_NAME] 배포된 적이 없다"
  exit 0
fi

row() {
  local color="$1" weight="$2" image state
  image="$(image_of "$color")"
  if is_running "app-$color"; then state="running"; else state="-"; fi
  printf '  %-6s %4s%%  %-8s %s\n' "$color" "$weight" "$state" "${image:--}"
}

echo "[$ENV_NAME] http://localhost:$ROUTER_PORT  (미리보기 http://localhost:$PREVIEW_PORT)"
echo "  색     트래픽  상태     이미지"
row blue "$BLUE_WEIGHT"
row green "$GREEN_WEIGHT"
echo "  live=$ACTIVE  롤백 대상=${ROLLBACK_COLOR:-없음}"

if [ -f "$STATE_DIR/history" ]; then
  echo "  최근 이력:"
  tail -n 5 "$STATE_DIR/history" | sed 's/^/    /'
fi
