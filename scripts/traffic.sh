#!/usr/bin/env bash
# 트래픽 비율을 손으로 바꾼다 (EP3 시연용).
#
#   ./scripts/traffic.sh <env> <blue 비율> <green 비율>
#   ./scripts/traffic.sh production 90 10
set -euo pipefail
. "$(dirname "$0")/lib.sh"

[ $# -eq 3 ] || die "사용법: traffic.sh <env> <blue 비율> <green 비율>"
load_env "$1"
BLUE="$2"
GREEN="$3"

if [ "$BLUE" -gt 0 ] && ! is_running app-blue; then die "app-blue가 떠 있지 않다"; fi
if [ "$GREEN" -gt 0 ] && ! is_running app-green; then die "app-green이 떠 있지 않다"; fi

set_traffic "$BLUE" "$GREEN"
save_state
ok "[$ENV_NAME] blue $BLUE : green $GREEN"
