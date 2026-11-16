# cicd-lab — CI/CD와 배포 전략 실습 리포

온라인 서점의 **주문 서비스**(Python 웹 앱 + PostgreSQL, 컨테이너로 배포) 하나로 CI/CD와 배포 전략 6편을 실습한다.
새 기능은 "주문 완료 화면에 예상 배송일 표시"다. 이 기능을 파이프라인으로 만들고, 환경을 거쳐, canary로 내보내고, 플래그로 켜고, 컬럼을 추가하고, 되돌린다.

| 편 | 주제 | 실습 파일 | 시연 순서 |
| --- | --- | --- | --- |
| EP1 | 파이프라인 설계 | `.github/workflows/pipeline.yml`, `Dockerfile`, `scripts/build.sh` | [docs/ep1-pipeline.md](docs/ep1-pipeline.md) |
| EP2 | 환경 분리 (dev / stg / prod) | `config/*.env`, `app/config.py`, `compose.yml` | [docs/ep2-environments.md](docs/ep2-environments.md) |
| EP3 | blue-green과 canary | `scripts/deploy.sh`, `scripts/traffic.sh`, `scripts/canary_check.py` | [docs/ep3-bluegreen-canary.md](docs/ep3-bluegreen-canary.md) |
| EP4 | feature flag | `flags.json`, `app/flags.py`, `scripts/check_flags.py` | [docs/ep4-feature-flag.md](docs/ep4-feature-flag.md) |
| EP5 | DB 무중단 마이그레이션 | `migrations/`, `app/migrate.py`, `app/backfill.py`(v1.1.0) | [docs/ep5-db-migration.md](docs/ep5-db-migration.md) |
| EP6 | 롤백 | `scripts/rollback.sh`, `.github/workflows/rollback.yml` | [docs/ep6-rollback.md](docs/ep6-rollback.md) |

편별 문서는 "화면에 띄울 파일 → 입력할 명령 → 기대 결과" 순서로 적혀 있다. 위에서 아래로 따라 하면 된다.

## 시작하기

필요한 것: Docker(Compose v2), Python 3.13, `uv`, `gh`(GitHub 시연용).

```bash
# 1. 개발 환경
uv venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt

# 2. 로컬 비밀 값 (.env.local은 커밋되지 않는다)
cp .env.local.example .env.local

# 3. CI의 test 단계와 같은 검사 (lint → flag 검사 → 테스트)
#    가상환경을 켜지 않아도 .venv를 직접 쓴다. 없으면 만든다.
./scripts/test.sh

# 4. 시연에 쓸 이미지 4개
./scripts/build.sh v1.0.0
./scripts/build.sh v1.1.0
./scripts/build.sh v1.2.0
./scripts/build.sh demo/ep3-bad-release v1.3.0-bad
```

## 버전

이미지는 git 태그에서 만든다. `./scripts/build.sh <태그>`는 그 커밋의 파일만 꺼내 빌드하므로 작업 디렉터리 상태와 무관하다.

| 이미지 | 내용 | DB 변경 |
| --- | --- | --- |
| `orders:v1.0.0` | 주문 생성·조회만 있는 기존 버전 | `orders`, `feature_flags` 테이블 |
| `orders:v1.1.0` | 예상 배송일 기능. 컬럼에 항상 쓰고, 화면 표시는 플래그 뒤에 있다 | **expand**: `estimated_delivery_date` 컬럼 추가 (NULL 허용) |
| `orders:v1.2.0` | NULL을 메우던 임시 코드 제거 | **contract**: `NOT NULL` (수동 적용) |
| `orders:v1.3.0-bad` | `demo/ep3-bad-release` 브랜치. 빠른 배송 주문이 500으로 실패한다. 테스트는 통과한다 | 없음 |

## 로컬 환경

환경 하나는 `DB 1 + 앱 2(blue, green) + 라우터(nginx) 1`이다. 세 환경 모두 같은 `compose.yml`을 쓰고 `config/<env>.env`만 다르다.

| 환경 | 서비스 | 미리보기(쉬는 색) | DB |
| --- | --- | --- | --- |
| dev | http://localhost:8081 | http://localhost:9081 | localhost:5441 |
| staging | http://localhost:8082 | http://localhost:9082 | localhost:5442 |
| production | http://localhost:8080 | http://localhost:9080 | localhost:5440 |

| 스크립트 | 하는 일 |
| --- | --- |
| `build.sh <ref> [버전]` | git ref로 이미지를 만든다 |
| `deploy.sh <env> <image> [--strategy bluegreen\|canary]` | 마이그레이션(expand) → 쉬는 색에 배포 → smoke test → 트래픽 전환 |
| `rollback.sh <env>` | 직전 버전으로 되돌린다. 컨테이너가 떠 있으면 라우터 전환만 한다 |
| `traffic.sh <env> <blue> <green>` | 트래픽 비율을 손으로 바꾼다 |
| `status.sh <env>` | 어느 색이 live인지, 각 색의 이미지, 최근 이력 |
| `run.sh <env> <모듈> ...` | live 컨테이너에서 `migrate`, `flagctl`, `backfill` 실행 |
| `psql.sh <env>` / `logs.sh <env>` | DB 접속 / 앱 로그 |
| `loadgen.py`, `canary_check.py` | 트래픽 생성과 색별 집계 / canary 진행·중단 판정 |
| `smoke_test.sh <url>` | 배포 직후 핵심 흐름 한 번 확인 |
| `check_flags.py` | 만료됐거나 등록되지 않은 플래그를 CI에서 잡는다 |
| `test.sh` | CI의 test 단계를 로컬에서 실행 |
| `setup-github.sh` | GitHub Environments(staging, production)와 승인자, secret 설정 |
| `teardown.sh <env\|all>` | 환경을 통째로 지운다 (촬영 전 초기화) |

`deploy.sh`의 배포 대상은 로컬 Docker다. Kubernetes나 ECS로 시연하려면 `scripts/lib.sh`의 `compose`, `set_traffic` 두 함수가 하는 일(컨테이너 띄우기, 트래픽 비율 바꾸기)을 해당 플랫폼 명령으로 바꾸면 된다.

## GitHub Actions

```
PR:    test ──▶ build(올리지 않음)
main:  test ──▶ build(GHCR에 push) ──▶ deploy-staging ──▶ [승인] ──▶ deploy-production(canary)
수동:  rollback (이미 만든 이미지를 다시 배포)
```

deploy job은 build job이 만든 이미지를 digest로 받아 **runner 안에서** `deploy.sh`를 실행한다. runner는 job이 끝나면 사라지므로 "배포된 환경"이 남지는 않는다. 파이프라인의 흐름(같은 아티팩트, 승인, canary 판정, 태그 이동)을 보여 주는 용도다.
각 환경에 떠 있는 버전은 GHCR의 `staging`, `production` 태그가 가리킨다. 직전 운영 버전은 `production-previous`다.
deploy job은 먼저 이 태그의 이미지를 올리고 contract 마이그레이션까지 적용해 "지금 환경의 상태"를 재현한 다음, 그 위에 새 이미지를 배포한다.

## 편별 실습 브랜치 (브랜치 하나, PR 하나)

편마다 미리 만들어 둔 브랜치를 PR로 올리고, 파이프라인이 어디서 어떻게 반응하는지 본다.

| 편 | 브랜치 | 바꾼 것 | 파이프라인에서 일어나는 일 |
| --- | --- | --- | --- |
| EP1 | `demo/ep1-pipeline` | 주문 화면에 안내 문구 한 줄 | PR은 test·build만. 머지하면 staging → 승인 → production까지 같은 digest로 통과 |
| EP1 | `demo/ep1-broken-test` | 일반 배송 예상일을 3일 → 2일 | `test`에서 멈춤. `build`는 시작도 안 함 (머지하지 않는다) |
| EP2 | `demo/ep2-missing-config` | `SUPPORT_EMAIL` 설정 추가. dev·staging에는 넣고 production에는 빠뜨림 | 테스트와 staging은 통과. `deploy-production`이 "설정 오류: SUPPORT_EMAIL"로 실패. live는 그대로 |
| EP3 | `demo/ep3-bad-release` | 배송일 계산 변경. 빠른 배송 주문이 500 | 테스트, staging, smoke test 통과. canary 10%에서 에러율 초과로 자동 중단 |
| EP4 | `demo/ep4-unregistered-flag` | 새 플래그 `show_tracking_link`를 코드에서만 쓰고 `flags.json`에 등록하지 않음 | `test`의 "Feature flag 검사"에서 멈춤. 등록하는 커밋을 더하면 통과 |
| EP5 | `demo/ep5-rename-column` | `book_title` → `title` 컬럼 이름을 마이그레이션 한 번으로 변경 | 테스트와 staging은 통과. production canary에서 **기존 버전** 에러율 100%로 중단. 되돌려도 복구되지 않음 |
| EP6 | `demo/ep6-wrong-date` | 예상 배송일 표기의 월·일이 뒤바뀜 | 전부 통과해 production까지 나감. `rollback` 워크플로로 되돌리고 revert로 roll-forward |

공통 순서:

```bash
# 1. PR을 올리고 test·build 결과를 본다
gh pr create --base main --head demo/ep3-bad-release --fill
gh pr checks --watch

# 2. 머지하면 main의 파이프라인이 staging, production으로 이어진다
gh pr merge demo/ep3-bad-release --squash
gh run watch          # deploy-production은 Actions 화면에서 승인해야 시작한다

# 3. 확인이 끝나면 main을 되돌린다 (이것도 파이프라인을 한 바퀴 돈다)
git switch main && git pull
git revert --no-edit HEAD && git push
```

- 한 번에 하나씩 한다. 다음 브랜치는 main을 되돌린 뒤에 올린다.
- 머지할 때 `--delete-branch`를 붙이지 않는다. 브랜치를 남겨 둬야 다시 쓸 수 있다.
- 같은 실습을 다시 하려면 새 브랜치에 커밋을 옮겨 PR을 만든다: `git switch -c retry/ep3 main && git cherry-pick demo/ep3-bad-release && git push -u origin retry/ep3`
- 편별 문서의 "GitHub에서 실습" 절에 볼 곳과 기대 결과가 있다.

## 촬영 전 준비

- [ ] `./scripts/teardown.sh all` 로 로컬 환경 초기화, 이미지 4개 빌드
- [ ] GitHub에 리포를 올리고 `./scripts/setup-github.sh` 실행 → Settings → Environments에 `staging`, `production`(Required reviewers)이 생겼는지 확인 (EP1·2)
- [ ] main에 한 번 push해서 파이프라인이 끝까지 도는지, `production` 태그가 생기는지 확인 (EP1·6)
- [ ] canary 그래프: `python3 scripts/loadgen.py --url http://localhost:8080 --watch --csv canary.csv` 를 켜 둔 채 EP3 시연을 한 번 돌리면 5초 구간별 에러율·p95가 CSV로 남는다 (EP3)
- [ ] EP5의 expand / contract SQL을 [docs/ep5-db-migration.md](docs/ep5-db-migration.md) 순서대로 한 번 실행

Required reviewers는 공개 리포이거나 유료 플랜의 비공개 리포에서만 설정된다.
