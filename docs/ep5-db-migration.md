# EP5 · DB 무중단 마이그레이션

**보여 줄 것**: `orders`에 `estimated_delivery_date NOT NULL` 컬럼을 서비스 중단 없이 넣는다. 한 번에 하지 않고 expand → backfill → contract로 나눈다.

| 단계 | DB | 떠 있는 코드 | 되돌릴 수 있나 |
| --- | --- | --- | --- |
| 0 | 컬럼 없음 | v1.0.0 | — |
| 1 expand | 컬럼 추가 (NULL 허용) | v1.0.0 + v1.1.0 | v1.0.0으로 가능 |
| 2 backfill | 기존 행 채움 | v1.1.0 | v1.0.0으로 가능 |
| 3 contract | NOT NULL | v1.1.0 + v1.2.0 | v1.1.0까지만 가능 |

## 화면에 띄울 파일

| 파일 | 볼 곳 |
| --- | --- |
| `migrations/0003_expand_add_estimated_delivery_date.sql` | NULL 허용, DEFAULT 없음, `lock_timeout` |
| `migrations/0004_contract_estimated_delivery_date_not_null.sql` | `NOT VALID` → `VALIDATE` → `SET NOT NULL` 세 단계 |
| `app/migrate.py` | `plan`: contract에서 멈춘다. `--allow-contract`로만 넘어간다 |
| `git show v1.1.0:app/web.py` | `delivery_date_of`: NULL이면 계산해서 메우는 임시 코드 |
| `git show v1.1.0:app/backfill.py` | 배치, `SKIP LOCKED`, 배치마다 commit |
| `git diff v1.1.0 v1.2.0 --stat` | contract 릴리스에서 임시 코드가 사라진다 |

## 준비

컬럼이 없는 v1.0.0에서 시작해 주문을 쌓는다.

```bash
./scripts/teardown.sh production
./scripts/deploy.sh production orders:v1.0.0
python3 scripts/loadgen.py --url http://localhost:8080 --requests 600
./scripts/psql.sh production -c '\d orders'
```

**터미널 2**에 트래픽을 계속 흘린다. 이 편 내내 에러율이 0%로 유지되는 것이 핵심이다.

```bash
python3 scripts/loadgen.py --url http://localhost:8080 --watch
```

## 시연 0 — 왜 그냥 ALTER 하면 안 되나 (잠금 대기열)

터미널 세 개에서 `./scripts/psql.sh production`으로 접속한다.

```sql
-- 터미널 A: 끝나지 않은 트랜잭션 (긴 리포트 쿼리라고 가정)
BEGIN;
SELECT count(*) FROM orders;

-- 터미널 B: 컬럼 추가. A가 끝나기를 기다리며 멈춘다
ALTER TABLE orders ADD COLUMN memo TEXT;

-- 터미널 C: 평범한 조회. B 뒤에 줄을 서서 함께 멈춘다
SELECT count(*) FROM orders;
```

이때 터미널 2의 요청 수가 0으로 떨어진다. ALTER 자체는 순식간이지만, 잠금을 기다리는 동안 뒤의 모든 쿼리가 막힌다.
터미널 A에서 `COMMIT;` 하면 전부 풀린다. 이제 `lock_timeout`을 걸고 다시 한다.

```sql
-- 터미널 A
BEGIN;
SELECT count(*) FROM orders;

-- 터미널 B: 2초 기다리다 스스로 포기한다. 서비스는 멈추지 않는다
SET lock_timeout = '2s';
ALTER TABLE orders ADD COLUMN memo2 TEXT;

-- 정리
-- 터미널 A
COMMIT;
-- 터미널 B
ALTER TABLE orders DROP COLUMN memo;
```

## 시연 1 — expand

```bash
cat migrations/0003_expand_add_estimated_delivery_date.sql
./scripts/deploy.sh production orders:v1.1.0 --strategy canary
```

- "1/4 마이그레이션"에서 `적용: 0003_expand_...`. 이 시점에 live는 아직 v1.0.0이다. 컬럼이 생겨도 v1.0.0은 모르는 채로 계속 동작한다.
- canary 단계에서는 두 버전이 함께 주문을 받는다. v1.0.0은 컬럼을 비워 두고, v1.1.0은 채운다.

```bash
./scripts/psql.sh production -c \
  'SELECT count(*) AS total, count(*) FILTER (WHERE estimated_delivery_date IS NULL) AS nulls FROM orders'
```

NULL인 행이 남아 있다. v1.1.0은 이 행을 읽을 때 계산해서 메운다(`delivery_date_of`).

## 시연 2 — contract를 너무 일찍 하면

```bash
./scripts/psql.sh production -1 -v ON_ERROR_STOP=1 \
  < migrations/0004_contract_estimated_delivery_date_not_null.sql
./scripts/psql.sh production -c '\d orders'
```

`VALIDATE CONSTRAINT`에서 실패하고 트랜잭션 전체가 취소된다. 컬럼은 여전히 NULL 허용이다.

## 시연 3 — backfill

```bash
./scripts/run.sh production backfill --batch-size 50 --sleep 0.5
./scripts/psql.sh production -c \
  'SELECT count(*) AS total, count(*) FILTER (WHERE estimated_delivery_date IS NULL) AS nulls FROM orders'
```

50건씩 나눠 채우고 배치마다 commit 한다. 도는 동안 터미널 2의 에러율과 p95는 그대로다. `nulls`가 0이 된다.

## 시연 4 — contract

contract 전에 두 가지를 확인한다.

```bash
# 1. 컬럼에 쓰지 않는 v1.0.0이 트래픽을 받고 있지 않다
./scripts/status.sh production
# 2. NULL이 없다 (위 쿼리)
```

contract 마이그레이션이 든 v1.2.0을 배포한다.

```bash
./scripts/deploy.sh production orders:v1.2.0
```

"1/4 마이그레이션"에 `보류: 0004_contract_... (contract 단계는 --allow-contract로 따로 적용한다)`가 나온다. 배포는 contract를 자동으로 적용하지 않는다.

```bash
./scripts/run.sh production migrate status
./scripts/run.sh production migrate up --allow-contract
./scripts/psql.sh production -c '\d orders'
```

`estimated_delivery_date`가 `not null`이다. 터미널 2의 에러율은 처음부터 끝까지 0%였다.

## 짚을 점

- 순서의 원칙: **DB를 먼저 넓히고, 코드를 바꾸고, 마지막에 DB를 좁힌다.** 각 시점에 떠 있는 모든 버전의 코드가 그 시점의 스키마와 호환된다.
- expand는 배포에 묶어 자동으로, contract는 사람이 확인하고 따로 적용한다. 파일 이름의 `expand` / `contract`로 구분한다.
- v1.2.0의 코드는 NULL을 메우지 않는다. backfill이 끝나기 전에 v1.2.0을 올리면 옛 주문의 조회가 실패한다. 그래서 순서가 backfill → v1.2.0이다.
- 테스트 DB는 마이그레이션 파일로 만든다(`tests/conftest.py`). 테스트가 통과하면 마이그레이션도 한 번 검증된 것이다.
- 코드는 `SELECT *` 대신 컬럼을 적는다(`app/store.py`). 스키마가 넓어져도 옛 코드가 영향을 받지 않는다.
