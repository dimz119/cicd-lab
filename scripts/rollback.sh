#!/usr/bin/env bash
# 직전 버전으로 되돌린다.
#
#   ./scripts/rollback.sh <env>
#
# 빠른 길: 직전 버전 컨테이너가 아직 떠 있으면 라우터만 전환한다 (수 초).
# 느린 길: 없으면 직전 이미지를 다시 배포한다. 다시 빌드하지는 않는다.
set -euo pipefail
. "$(dirname "$0")/lib.sh"

[ $# -eq 1 ] || die "사용법: rollback.sh <env>"
load_env "$1"
[ -n "$ACTIVE" ] || die "[$ENV_NAME] 배포된 적이 없다"

STARTED="$(date +%s)"

if [ -n "$ROLLBACK_COLOR" ] && is_running "app-$ROLLBACK_COLOR"; then
  TARGET="$ROLLBACK_COLOR"
  FROM_IMAGE="$(image_of "$ACTIVE")"
  log "[$ENV_NAME] 라우터 전환: $ACTIVE ($FROM_IMAGE) → $TARGET ($(image_of "$TARGET"))"
  set_traffic_to "$TARGET" 100 "$ACTIVE"

  # 되돌린 뒤에는 방금 내린 버전이 '직전 버전'이 된다.
  ROLLBACK_COLOR="$ACTIVE"
  PREVIOUS_IMAGE="$FROM_IMAGE"
  ACTIVE="$TARGET"
  save_state
  record "rolled-back" "$TARGET" "$(image_of "$TARGET")"
  ok "[$ENV_NAME] 롤백 완료: $(image_of "$TARGET") ($TARGET), $(( $(date +%s) - STARTED ))초"
elif [ -n "$PREVIOUS_IMAGE" ]; then
  warn "직전 버전 컨테이너가 없어 이미지를 다시 배포한다: $PREVIOUS_IMAGE"
  "$ROOT/scripts/deploy.sh" "$ENV_NAME" "$PREVIOUS_IMAGE" --strategy bluegreen
  ok "[$ENV_NAME] 롤백 완료 (재배포), $(( $(date +%s) - STARTED ))초"
else
  die "[$ENV_NAME] 되돌릴 직전 버전이 없다"
fi
