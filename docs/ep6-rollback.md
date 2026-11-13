# EP6 · 롤백

**보여 줄 것**: 되돌리기는 사고가 난 뒤에 궁리하는 것이 아니라 앞의 다섯 편에서 미리 만들어 둔 것이다. 수단마다 속도와 범위가 다르고, 되돌릴 수 없는 지점이 있다.

| 수단 | 되돌리는 것 | 걸리는 시간 | 준비물 (어느 편) |
| --- | --- | --- | --- |
| 플래그 끄기 | 기능 하나 | 수 초, 배포 없음 | feature flag (EP4) |
| 라우터 전환 | 버전 전체 | 1초 | 옛 버전을 내리지 않는 blue-green (EP3) |
| 옛 이미지 재배포 | 버전 전체 | 수십 초, 빌드 없음 | 버전별로 보관된 아티팩트 (EP1) |
| roll-forward | 고친 새 버전 | 파이프라인 한 바퀴 | 빠르고 믿을 수 있는 파이프라인 (EP1) |

## 화면에 띄울 파일

| 파일 | 볼 곳 |
| --- | --- |
| `scripts/rollback.sh` | 빠른 길(라우터 전환)과 느린 길(재배포)의 분기 |
| `scripts/deploy.sh` | 마지막 부분: 방금까지 live였던 색을 `ROLLBACK_COLOR`로 남긴다 |
| `.github/workflows/rollback.yml` | test도 build도 없다. 태그를 digest로 고정한 뒤 배포한다 |
| `app/migrate.py` | "DB가 이 이미지보다 앞서 있다": 롤백해도 expand는 되돌리지 않는다 |

## 준비

EP5에 이어 production의 live는 v1.2.0, contract까지 적용된 상태다. 플래그를 켜 둔다.

```bash
./scripts/run.sh production flagctl set show_estimated_delivery on
./scripts/status.sh production
```

**터미널 2**:

```bash
python3 scripts/loadgen.py --url http://localhost:8080 --watch
```

## 시연 1 — 가장 빠른 되돌리기: 플래그

"예상 배송일이 틀리게 나온다"는 제보가 들어왔다고 가정한다. 원인은 아직 모른다.

```bash
./scripts/run.sh production flagctl set show_estimated_delivery off
```

5초 안에 화면에서 사라진다. 배포 이력에는 아무것도 남지 않는다. 버전은 그대로다.

```bash
./scripts/status.sh production
```

## 시연 2 — 라우터 전환

급해서 canary를 건너뛰고 나쁜 버전을 한 번에 내보낸다.

```bash
./scripts/deploy.sh production orders:v1.3.0-bad
```

smoke test는 통과하고 100% 전환된다. 터미널 2에 에러율이 올라온다. 이번에는 사용자 전원이 겪는다.

```bash
./scripts/rollback.sh production
./scripts/status.sh production
```

1초. 옛 버전 컨테이너가 떠 있었기 때문이다. 터미널 2의 에러율이 다음 구간에 0%로 돌아온다.

## 시연 3 — 옛 이미지 재배포

돌아갈 컨테이너가 없거나 두 버전 이상 전으로 가야 하면 보관된 이미지를 다시 배포한다.

```bash
./scripts/deploy.sh production orders:v1.1.0
```

- 빌드가 없다. 그때 테스트를 통과한 바로 그 이미지다.
- "1/4 마이그레이션"에 `DB가 이 이미지보다 앞서 있다 (이 이미지가 모르는 버전: 0004)`. 코드는 옛 버전으로 가도 DB는 되돌리지 않는다. v1.1.0은 컬럼에 값을 쓰므로 NOT NULL 스키마에서도 동작한다.

## 시연 4 — 되돌릴 수 없는 지점

같은 방법으로 v1.0.0까지 가 본다.

```bash
./scripts/deploy.sh production orders:v1.0.0
./scripts/status.sh production
```

smoke test의 "주문 생성"에서 실패한다. v1.0.0은 `estimated_delivery_date` 없이 INSERT 하는데 contract 이후에는 거부된다.
배포 스크립트는 live를 건드리지 않고 멈췄다. contract가 v1.0.0으로 가는 길을 닫았다는 것을 EP5의 표에서 다시 짚는다.

## 시연 5 — roll-forward

되돌린 뒤에는 고쳐서 다시 나간다. 고친 버전도 같은 파이프라인을 처음부터 통과한다.

```bash
git switch -c hotfix demo/bad-release
git revert --no-edit HEAD
./scripts/test.sh
./scripts/build.sh hotfix v1.3.1
git switch main && git branch -D hotfix

./scripts/deploy.sh production orders:v1.3.1 --strategy canary
```

이번에는 canary를 건너뛰지 않는다. 세 단계 모두 `판정: 진행`.

## 시연 6 — GitHub Actions의 rollback

```bash
gh workflow run rollback.yml -f tag=production-previous
gh run watch
```

- job이 하나다. test와 build가 없다.
- `production` environment의 승인을 거친다.
- 끝나면 `production` 태그가 되돌린 이미지를 가리킨다. GHCR의 Packages 화면에서 태그가 옮겨진 것을 보여 준다.

## 롤백이냐 roll-forward냐

| 상황 | 선택 |
| --- | --- |
| 원인을 모른다, 영향이 크다 | 롤백 먼저. 원인 분석은 그다음 |
| 기능 하나만 문제다 | 플래그를 끈다 |
| 돌아갈 버전이 지금 스키마·데이터와 호환되지 않는다 (contract 이후) | roll-forward |
| 원인이 명확하고 수정이 한 줄이며 파이프라인이 빠르다 | roll-forward도 가능 |

## 짚을 점

- 롤백은 "새 배포"다. 이력(`status.sh`의 최근 이력)에 남고, 같은 스크립트와 같은 smoke test를 탄다.
- 롤백 뒤 다시 `rollback.sh`를 실행하면 방금 내린 버전으로 돌아간다. 직전 버전은 항상 "바로 전에 live였던 것"이다.
- 코드는 되돌려도 데이터는 되돌아가지 않는다. 나쁜 버전이 쓴 행은 남는다. 그래서 DB 변경은 expand / contract로 나눠 되돌릴 필요가 없게 만든다.
- 롤백 절차는 평소에 써 봐야 한다. 사고 때 처음 실행하는 스크립트는 믿을 수 없다.
