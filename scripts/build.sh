#!/usr/bin/env bash
# 이미지를 만든다.
#
#   ./scripts/build.sh              현재 커밋(HEAD)으로 빌드
#   ./scripts/build.sh v1.0.0       태그나 브랜치로 빌드
#   ./scripts/build.sh worktree     커밋하지 않은 작업 디렉터리로 빌드
#   ./scripts/build.sh demo/bad-release v1.3.0-bad    버전 이름을 직접 지정
#
# 결과 이미지: orders:<버전>
set -euo pipefail
. "$(dirname "$0")/lib.sh"

REF="${1:-HEAD}"
cd "$ROOT"

if [ "$REF" = "worktree" ]; then
  VERSION="$(git describe --tags --always 2>/dev/null || echo dev)-wip"
  log "작업 디렉터리 → orders:$VERSION"
  docker build -q --build-arg "APP_VERSION=$VERSION" -t "orders:$VERSION" . >/dev/null
else
  VERSION="${2:-$(git describe --tags --always "$REF")}"
  log "$REF → orders:$VERSION"
  # git archive로 그 커밋의 파일만 꺼내 빌드한다.
  # 작업 디렉터리에 뭐가 있든 같은 커밋이면 같은 내용이 들어간다.
  git archive "$REF" | docker build -q --build-arg "APP_VERSION=$VERSION" -t "orders:$VERSION" - >/dev/null
fi

ok "orders:$VERSION"
