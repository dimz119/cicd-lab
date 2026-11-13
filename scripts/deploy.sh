#!/usr/bin/env bash
# 이미지 하나를 환경 하나에 배포한다.
#
#   ./scripts/deploy.sh <env> <image> [--strategy bluegreen|canary] [--steps "10 50 100"]
#
# 순서:
#   1. 새 이미지로 마이그레이션 (expand 단계만)
#   2. 쉬고 있는 색에 새 이미지를 띄운다
#   3. 미리보기 포트로 smoke test
#   4. 트래픽을 넘긴다 (bluegreen: 한 번에, canary: 단계별로 지표를 보며)
#
# 옛 버전 컨테이너는 내리지 않는다. 그래야 롤백이 라우터 전환 한 번으로 끝난다.
set -euo pipefail
. "$(dirname "$0")/lib.sh"

USAGE='사용법: deploy.sh <env> <image> [--strategy bluegreen|canary] [--steps "10 50 100"]'
[ $# -ge 2 ] || die "$USAGE"

load_env "$1"
IMAGE="$2"
shift 2

STRATEGY="bluegreen"
STEPS="10 50 100"
while [ $# -gt 0 ]; do
  case "$1" in
    --strategy) STRATEGY="$2"; shift 2 ;;
    --steps)    STEPS="$2"; shift 2 ;;
    *) die "$USAGE" ;;
  esac
done
case "$STRATEGY" in
  bluegreen|canary) ;;
  *) die "--strategy는 bluegreen 또는 canary" ;;
esac

if [ -z "$ACTIVE" ]; then
  FIRST_DEPLOY=1
  TARGET="blue"
else
  FIRST_DEPLOY=0
  TARGET="$(other_color "$ACTIVE")"
fi

log "[$ENV_NAME] $IMAGE → $TARGET ($STRATEGY)"

# 배포가 중간에 실패하면 live는 건드리지 않은 채로 끝낸다.
TARGET_REPLACED=0
fail() {
  record "$1" "$TARGET" "$IMAGE"
  if [ "$TARGET_REPLACED" -eq 1 ]; then
    # 쉬던 색에는 이제 검증에 실패한 버전이 있다.
    # 라우터 전환으로 돌아갈 곳이 아니므로 표시를 지운다.
    ROLLBACK_COLOR=""
  else
    set_image "$TARGET" "$OLD_TARGET_IMAGE"
  fi
  save_state
  die "$2"
}

compose up -d --wait db >/dev/null

# 쉬는 색으로 가는 트래픽이 없는지 먼저 확실히 한다.
if [ "$FIRST_DEPLOY" -eq 0 ]; then
  set_traffic_to "$ACTIVE" 100
fi
OLD_TARGET_IMAGE="$(image_of "$TARGET")"
set_image "$TARGET" "$IMAGE"

log "1/4 마이그레이션 (expand 단계만)"
compose run --rm --no-deps -T "app-$TARGET" python -m app.migrate up \
  || fail "failed" "마이그레이션 실패. live는 그대로다."

log "2/4 $TARGET 에 새 버전을 띄운다"
TARGET_REPLACED=1
compose up -d --no-deps --force-recreate --wait "app-$TARGET" >/dev/null 2>&1 \
  || { compose logs --tail 20 "app-$TARGET" >&2; fail "failed" "새 버전이 준비 상태가 되지 못했다. live는 그대로다."; }
save_state

log "3/4 smoke test (미리보기 포트 $PREVIEW_PORT)"
if [ "$FIRST_DEPLOY" -eq 1 ]; then
  # 첫 배포는 넘겨받을 옛 버전이 없다.
  set_traffic_to "$TARGET" 100 "$TARGET"
else
  set_traffic_to "$ACTIVE" 100 "$TARGET"
fi
"$ROOT/scripts/smoke_test.sh" "http://localhost:$PREVIEW_PORT" \
  || fail "failed" "smoke test 실패. live는 그대로다."

log "4/4 트래픽 전환"
if [ "$FIRST_DEPLOY" -eq 1 ]; then
  ok "첫 배포: $TARGET 100%"
elif [ "$STRATEGY" = "bluegreen" ]; then
  set_traffic_to "$TARGET" 100 "$ACTIVE"
  ok "$ACTIVE → $TARGET 전환 (100%)"
else
  for PERCENT in $STEPS; do
    set_traffic_to "$TARGET" "$PERCENT" "$TARGET"
    log "canary $PERCENT% — 지표 확인"
    if [ "$PERCENT" -lt 100 ]; then
      CHECK_ARGS="--baseline-color $ACTIVE"
    else
      CHECK_ARGS=""
    fi
    # shellcheck disable=SC2086
    if ! python3 "$ROOT/scripts/canary_check.py" --url "http://localhost:$ROUTER_PORT" \
        --canary-color "$TARGET" $CHECK_ARGS; then
      # 기준을 넘으면 사람을 기다리지 않고 바로 0%로 되돌린다.
      set_traffic_to "$ACTIVE" 100 "$TARGET"
      fail "aborted" "canary 중단: $PERCENT% 단계에서 기준 초과. 트래픽을 $ACTIVE 100%로 되돌렸다."
    fi
  done
  set_traffic_to "$TARGET" 100 "$ACTIVE"
  ok "canary 완료: $TARGET 100%"
fi

# 방금까지 live였던 색이 롤백할 곳이 된다.
if [ "$FIRST_DEPLOY" -eq 1 ]; then
  ROLLBACK_COLOR=""
  PREVIOUS_IMAGE=""
else
  ROLLBACK_COLOR="$ACTIVE"
  PREVIOUS_IMAGE="$(image_of "$ACTIVE")"
fi
ACTIVE="$TARGET"
save_state
record "deployed" "$TARGET" "$IMAGE"

ok "[$ENV_NAME] 배포 완료: $IMAGE ($TARGET) → http://localhost:$ROUTER_PORT"
