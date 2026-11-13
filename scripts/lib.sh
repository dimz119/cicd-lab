#!/usr/bin/env bash
# 배포 스크립트들이 함께 쓰는 함수 모음.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log()  { printf '\033[1;34m▶ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[1;31m✘ %s\033[0m\n' "$*" >&2; exit 1; }

# 환경 설정과 배포 상태를 읽는다.
load_env() {
  ENV_NAME="${1:-}"
  case "$ENV_NAME" in
    dev|staging|production) ;;
    *) die "환경은 dev, staging, production 중 하나여야 한다 (입력: '${ENV_NAME}')" ;;
  esac

  # 비밀이 아닌 설정은 리포의 config/<env>.env에서 온다.
  set -a
  # shellcheck disable=SC1090
  . "$ROOT/config/$ENV_NAME.env"
  set +a

  # 비밀 값은 리포 밖에서 온다.
  # CI에서는 Environment secret, 로컬에서는 .env.local이다.
  if [ -z "${DB_PASSWORD:-}" ] && [ -f "$ROOT/.env.local" ]; then
    # shellcheck disable=SC1091
    . "$ROOT/.env.local"
  fi
  if [ -z "${DB_PASSWORD:-}" ]; then
    warn "DB_PASSWORD가 없어 실습용 기본값을 쓴다"
    DB_PASSWORD="lab-only-password"
  fi
  export DB_PASSWORD

  STATE_DIR="$ROOT/.deploy/$ENV_NAME"
  mkdir -p "$STATE_DIR/nginx"

  # 배포 상태: 어느 색이 live인지, 각 색에 어떤 이미지가 올라가 있는지.
  ACTIVE=""
  BLUE_IMAGE=""
  GREEN_IMAGE=""
  BLUE_WEIGHT=0
  GREEN_WEIGHT=0
  ROLLBACK_COLOR=""
  PREVIOUS_IMAGE=""
  if [ -f "$STATE_DIR/state" ]; then
    # shellcheck disable=SC1091
    . "$STATE_DIR/state"
  fi
  export BLUE_IMAGE GREEN_IMAGE
}

save_state() {
  cat > "$STATE_DIR/state" <<STATE
ACTIVE="$ACTIVE"
BLUE_IMAGE="$BLUE_IMAGE"
GREEN_IMAGE="$GREEN_IMAGE"
BLUE_WEIGHT=$BLUE_WEIGHT
GREEN_WEIGHT=$GREEN_WEIGHT
ROLLBACK_COLOR="$ROLLBACK_COLOR"
PREVIOUS_IMAGE="$PREVIOUS_IMAGE"
STATE
}

# 배포 이력을 한 줄 남긴다.
record() {
  printf '%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$3" >> "$STATE_DIR/history"
}

compose() {
  docker compose --progress quiet -p "orders-$ENV_NAME" -f "$ROOT/compose.yml" "$@"
}

other_color() {
  if [ "$1" = "blue" ]; then echo "green"; else echo "blue"; fi
}

image_of() {
  if [ "$1" = "blue" ]; then echo "$BLUE_IMAGE"; else echo "$GREEN_IMAGE"; fi
}

set_image() {
  if [ "$1" = "blue" ]; then BLUE_IMAGE="$2"; else GREEN_IMAGE="$2"; fi
  export BLUE_IMAGE GREEN_IMAGE
}

is_running() {
  [ -n "$(compose ps --status running -q "$1" 2>/dev/null)" ]
}

# 트래픽 비율을 바꾼다.
# set_traffic <blue 비율> <green 비율> [미리보기 포트에 연결할 색]
set_traffic() {
  local blue="$1" green="$2" preview="${3:-}"
  local conf="$STATE_DIR/nginx/default.conf"

  if [ "$blue" -eq 0 ] && [ "$green" -eq 0 ]; then
    die "blue와 green 비율이 모두 0일 수는 없다"
  fi

  {
    echo "# scripts/lib.sh의 set_traffic이 만든 파일이다. 직접 고치지 않는다."
    echo "upstream orders_live {"
    if [ "$blue" -gt 0 ];  then echo "    server app-blue:8000 weight=$blue;"; fi
    if [ "$green" -gt 0 ]; then echo "    server app-green:8000 weight=$green;"; fi
    echo "}"
    echo
    echo "server {"
    echo "    listen 80;"
    echo "    location / {"
    echo "        proxy_pass http://orders_live;"
    echo "        proxy_set_header Host \$http_host;"
    echo "    }"
    echo "}"
    if [ -n "$preview" ]; then
      echo
      echo "# 아직 트래픽을 받지 않는 색을 미리 확인하는 포트."
      echo "server {"
      echo "    listen 8081;"
      echo "    location / {"
      echo "        proxy_pass http://app-$preview:8000;"
      echo "        proxy_set_header Host \$http_host;"
      echo "    }"
      echo "}"
    fi
  } > "$conf.tmp"
  mv "$conf.tmp" "$conf"

  if is_running router; then
    # reload는 처리 중인 요청을 끊지 않고 새 설정으로 넘어간다.
    compose exec -T router nginx -t -q
    compose exec -T router nginx -s reload 2>/dev/null
    sleep 1
  else
    compose up -d --no-deps --wait router >/dev/null
  fi

  BLUE_WEIGHT="$blue"
  GREEN_WEIGHT="$green"
}

# set_traffic_to <색> <그 색의 비율(%)> [미리보기 색]
set_traffic_to() {
  local color="$1" percent="$2" preview="${3:-}"
  if [ "$color" = "blue" ]; then
    set_traffic "$percent" "$((100 - percent))" "$preview"
  else
    set_traffic "$((100 - percent))" "$percent" "$preview"
  fi
}
