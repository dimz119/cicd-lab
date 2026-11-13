# EP2 · 환경 분리 (dev / stg / prod)

**보여 줄 것**: 환경마다 **같아야 하는 것**(이미지, 구성, 배포 절차)과 **달라야 하는 것**(설정, 비밀 값, 데이터)을 나눈다.

## 화면에 띄울 파일

| 파일 | 볼 곳 |
| --- | --- |
| `config/dev.env`, `staging.env`, `production.env` | 세 파일의 차이. 비밀 값은 없다 |
| `app/config.py` | 환경 변수만 읽는다. 잘못되면 시작할 때 죽는다 |
| `compose.yml` | 세 환경이 이 파일 하나를 쓴다. `DATABASE_URL`은 배포할 때 조립된다 |
| `.env.local.example`, `.gitignore` | 비밀 값이 들어오는 길 |

## 시연 순서

EP1에서 staging과 production에 `orders:v1.1.0`이 올라가 있다. dev를 더한다.

```bash
./scripts/deploy.sh dev orders:v1.1.0
```

**1. 같은 것: 이미지와 구성**

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}' | grep orders- | sort
```

세 환경 모두 `db`, `app-blue`, `router`로 구성이 같고 이미지도 같다.

**2. 다른 것: 설정**

```bash
diff config/staging.env config/production.env
for port in 8081 8082 8080; do curl -s localhost:$port/info; echo; done
```

`version`은 같고 `env`, `log_level`, `payment_api_url`이 다르다. staging은 production과 거의 같고 결제만 sandbox다.

**3. 설정의 차이가 동작의 차이로**

```bash
curl -s -X POST localhost:8081/orders -H 'Content-Type: application/json' \
  -d '{"user_id":"user-1","book_title":"환경 분리","quantity":1}'
curl -s -X POST localhost:8080/orders -H 'Content-Type: application/json' \
  -d '{"user_id":"user-1","book_title":"환경 분리","quantity":1}'

./scripts/logs.sh dev
./scripts/logs.sh production
```

dev(`LOG_LEVEL=DEBUG`)에는 `create_order` 이벤트와 health check 로그까지 남고, production에는 요청 로그만 남는다.

**4. 비밀 값은 리포에 없다**

```bash
git grep -n "DB_PASSWORD"
cat .env.local.example
curl -s localhost:8080/info
```

- 리포에는 `${DB_PASSWORD}` 자리만 있다.
- 로컬은 `.env.local`, GitHub Actions는 Environment secret에서 값이 들어온다.
- `/info`는 `DATABASE_URL`을 내보내지 않는다.
- GitHub 화면: Settings → Environments → `staging` / `production` 각각에 이름이 같은 `DB_PASSWORD`가 있고 값은 서로 다르다. `pipeline.yml`의 `environment: staging` 한 줄이 어느 값을 쓸지 정한다.

**5. 설정이 틀리면 요청을 받기 전에 죽는다**

```bash
docker run --rm -e APP_ENV=prod orders:v1.1.0 python -m app.migrate status
```

`APP_ENV` 오타, 빠진 `DATABASE_URL`, `PAYMENT_API_URL`을 한 번에 알려 준다.

**6. 데이터와 플래그 상태도 환경마다 따로**

```bash
./scripts/run.sh staging flagctl set show_estimated_delivery on
./scripts/run.sh staging flagctl list
./scripts/run.sh production flagctl list
```

staging에서만 켜진다. 플래그 정의는 리포(`flags.json`)에, 켜짐/꺼짐은 각 환경의 DB에 있다. EP4에서 이어진다.

## 짚을 점

- "staging에서는 됐는데"를 줄이려면 다른 것을 최소로 줄이고, 그 목록을 `config/`에서 한눈에 볼 수 있게 한다.
- 환경 이름으로 분기하는 코드(`if env == "production"`)를 쓰지 않는다. 값을 설정으로 뺀다.
- 한 번 만든 환경의 `DB_PASSWORD`를 바꾸면 기존 DB 볼륨과 맞지 않는다. 실습에서는 `./scripts/teardown.sh <env>` 후 다시 배포한다.
