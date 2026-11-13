# EP3 · blue-green과 canary

**보여 줄 것**: 새 버전을 옛 버전 옆에 띄우고 트래픽만 옮긴다. canary는 일부만 먼저 보내고 지표로 진행·중단을 정한다.

## 화면에 띄울 파일

| 파일 | 볼 곳 |
| --- | --- |
| `scripts/deploy.sh` | "4/4 트래픽 전환"의 bluegreen / canary 분기 |
| `scripts/lib.sh` | `set_traffic`: nginx upstream의 `weight`를 바꾸고 reload 한다 |
| `.deploy/production/nginx/default.conf` | 지금 적용된 비율 (스크립트가 생성) |
| `scripts/canary_check.py` | `judge`: baseline과 비교해 판정한다 |

## 준비

```bash
./scripts/teardown.sh production
./scripts/deploy.sh production orders:v1.0.0
```

**터미널 2**에 지표 화면을 띄워 둔다. 5초마다 색별 요청 수, 에러율, p95가 나온다.

```bash
python3 scripts/loadgen.py --url http://localhost:8080 --watch
```

브라우저에서 http://localhost:8080 을 열면 화면 아래에 응답한 버전과 색이 보인다.

## 시연 1 — blue-green

```bash
./scripts/deploy.sh production orders:v1.1.0
./scripts/status.sh production
```

- 터미널 2: `blue v1.0.0 100%`가 한 구간 만에 `green v1.1.0 100%`로 바뀐다. 에러율은 0%다.
- 전환 전에 미리보기 포트(9080)로 smoke test를 통과해야 한다.
- blue 컨테이너는 내리지 않았다. `status`의 `롤백 대상=blue`.

```bash
cat .deploy/production/nginx/default.conf
curl -s localhost:9080/info
```

미리보기 포트는 이제 쉬고 있는 옛 버전(v1.0.0)을 가리킨다. 그래서 되돌리기가 전환 한 번이다.

```bash
./scripts/rollback.sh production
```

1초 안에 끝난다. 다음 시연을 위해 live는 v1.0.0(blue)인 상태로 둔다.

## 시연 2 — canary를 손으로

green에는 v1.1.0이 떠 있다. 비율만 바꾼다.

```bash
./scripts/traffic.sh production 90 10
./scripts/traffic.sh production 50 50
./scripts/traffic.sh production 100 0
```

터미널 2에서 두 색이 같은 시간대에 나란히 집계되는 것을 보여 준다. canary의 지표는 이 옆줄(baseline)과 비교한다.

## 시연 3 — canary 자동 진행

```bash
./scripts/deploy.sh production orders:v1.1.0 --strategy canary
```

10% → 50% → 100% 단계마다 표와 `판정: 진행`이 출력된다.

## 시연 4 — canary 자동 중단

`v1.3.0-bad`는 테스트와 smoke test를 통과하지만 빠른 배송 주문에서 500을 낸다.

```bash
git diff v1.2.0 demo/bad-release -- app/delivery.py
./scripts/deploy.sh production orders:v1.3.0-bad --strategy canary
```

- smoke test는 통과한다 (일반 배송 주문 하나만 넣어 보므로).
- 10% 단계에서 canary 에러율이 baseline + 2%p를 넘어 `판정: 중단`.
- 스크립트가 트래픽을 기존 버전 100%로 되돌리고 종료 코드 1로 끝난다.

```bash
./scripts/status.sh production
./scripts/logs.sh production | grep '"status": 500' | tail -3
```

이력에 `aborted`가 남고 live는 v1.1.0 그대로다. 사용자의 10%만, 수 초 동안 영향을 받았다.

## 짚을 점

- blue-green은 전환이 한 번에 일어난다. 문제가 있으면 전원이 겪는다. 대신 단순하고 되돌리기가 빠르다.
- canary는 영향 범위를 비율로 제한한다. 대신 두 버전이 동시에 트래픽을 받으므로 서로 호환돼야 한다 (EP5).
- 판정 기준은 `canary_check.py`의 기본값이다: 에러율은 baseline + 2%p, p95는 baseline의 2배(최소 200ms), 표본 20건 미만이면 진행하지 않는다.
- 실습의 지표는 `loadgen.py`가 만든 합성 트래픽을 응답 헤더(`X-App-Color`)로 나눠 센 것이다. 실제로는 모니터링 시스템의 버전별 지표를 쓴다.
- GitHub에서 보려면 `demo/bad-release`를 PR로 올려 머지한다. `deploy-production` job이 canary 단계에서 실패하고 `production` 태그는 움직이지 않는다. 그 뒤 revert PR로 정리한다.
