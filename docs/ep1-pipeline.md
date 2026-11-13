# EP1 · 파이프라인 설계

**보여 줄 것**: 빌드는 한 번만 하고, 같은 아티팩트가 test → staging → production을 차례로 통과한다.

## 화면에 띄울 파일

| 파일 | 볼 곳 |
| --- | --- |
| `.github/workflows/pipeline.yml` | job 4개와 `needs`로 이어진 순서. `build`의 `outputs.image`를 뒤의 job이 받는 부분 |
| `Dockerfile` | `ARG APP_VERSION`: 버전은 빌드할 때 한 번 박힌다. 환경별 값은 이미지에 없다 |
| `scripts/build.sh` | `git archive`로 커밋의 파일만 꺼내 빌드한다 |
| `scripts/deploy.sh` | 맨 위 주석의 4단계. 인자가 `<env> <image>` 둘뿐이다 |

## 시연 1 — 로컬에서 파이프라인을 손으로 따라가기

```bash
./scripts/teardown.sh all

# 1단계 test: CI와 같은 검사
./scripts/test.sh

# 2단계 build: 한 번만
./scripts/build.sh v1.1.0
docker image inspect orders:v1.1.0 --format '{{.Id}}'

# 3단계: 같은 이미지를 staging에
./scripts/deploy.sh staging orders:v1.1.0

# 4단계: 같은 이미지를 production에
./scripts/deploy.sh production orders:v1.1.0
```

같은 아티팩트인지 확인한다. 두 환경의 컨테이너가 같은 이미지 ID를 쓴다.

```bash
docker inspect orders-staging-app-blue-1 orders-production-app-blue-1 --format '{{.Name}} {{.Image}}'
curl -s localhost:8082/info
curl -s localhost:8080/info
```

`version`은 같고 `env`만 다르다. 환경마다 다시 빌드했다면 이 보장이 없다.

## 시연 2 — GitHub Actions

준비: 리포를 GitHub에 올리고 `./scripts/setup-github.sh`를 한 번 실행한다.

1. **PR에서는 test와 build만 돈다.**

   ```bash
   git switch -c demo/ep1-readme
   echo "" >> README.md
   git commit -am "docs: 파이프라인 시연" && git push -u origin demo/ep1-readme
   gh pr create --fill
   ```

   Actions 탭에서 `deploy-staging`, `deploy-production`이 건너뛰어진 것을 보여 준다.

2. **머지하면 같은 파이프라인이 끝까지 이어진다.**

   ```bash
   gh pr merge --squash --delete-branch
   gh run watch
   ```

   - `build` job의 Summary: 이미지 태그와 digest
   - `deploy-staging` 로그의 `[staging] ghcr.io/...@sha256:...` 과 `deploy-production` 로그의 digest가 같다
   - `deploy-production`은 "Review deployments" 승인을 기다린다. 승인하면 canary 단계가 돈다

3. **앞 단계가 실패하면 뒤 단계는 시작하지 않는다.**

   ```bash
   git switch -c demo/ep1-lint
   echo "import os" >> app/delivery.py
   git commit -am "demo: lint 실패" && git push -u origin demo/ep1-lint
   gh pr create --fill
   ```

   `test`의 Lint step에서 멈추고 `build`는 시작도 하지 않는다. 확인 후 PR을 닫는다.

   ```bash
   gh pr close --delete-branch demo/ep1-lint && git switch main
   ```

## 짚을 점

- 파이프라인 단계는 싼 것부터: lint(초) → 테스트(수십 초) → 빌드 → 배포.
- `build`는 PR에서도 돈다. 올리지는 않고 Dockerfile이 깨지지 않았는지만 본다.
- 뒤의 job은 태그가 아니라 digest(`@sha256:...`)로 이미지를 받는다. 태그는 다른 이미지로 옮겨 붙을 수 있다.
- 마이그레이션 파일과 `flags.json`도 이미지에 들어 있다. 코드와 함께 한 덩어리로 움직인다.
