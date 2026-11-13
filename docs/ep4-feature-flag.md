# EP4 · feature flag

**보여 줄 것**: 배포(코드가 서버에 올라감)와 출시(사용자가 기능을 봄)를 떼어낸다. 그리고 플래그가 쌓여 빚이 되지 않게 관리한다.

## 화면에 띄울 파일

| 파일 | 볼 곳 |
| --- | --- |
| `flags.json` | 플래그의 정의: 설명, 담당자, 만료일, 기본값 |
| `app/flags.py` | `is_enabled`, `bucket`(사용자별로 고정된 0~99) |
| `app/web.py` | `order_complete`의 `flags.is_enabled(...)` 한 줄. `create_order`는 플래그와 무관하게 컬럼에 쓴다 |
| `app/templates/complete.html` | `{% if estimated_delivery_date %}` |
| `scripts/check_flags.py` | CI가 잡는 네 가지 |

## 준비

EP3에 이어 production의 live는 v1.1.0이다. 처음부터 하려면:

```bash
./scripts/teardown.sh production
./scripts/deploy.sh production orders:v1.1.0
```

사용자 20명의 주문을 하나씩 만든다.

```bash
for i in $(seq 1 20); do
  curl -s -o /dev/null -X POST localhost:8080/orders -H 'Content-Type: application/json' \
    -d "{\"user_id\":\"user-$i\",\"book_title\":\"feature flag 실전\",\"quantity\":1}"
done
./scripts/psql.sh production -c 'SELECT id, user_id FROM orders ORDER BY id DESC LIMIT 20'
```

아래에서 쓸 함수. 방금 만든 주문 20개의 완료 화면에 예상 배송일이 보이는지 센다.

```bash
show() {
  for id in $(./scripts/psql.sh production -Atc 'SELECT id FROM orders ORDER BY id DESC LIMIT 20'); do
    curl -s localhost:8080/orders/$id/complete | grep -c '예상 배송일'
  done | tr '\n' ' '; echo
}
```

## 시연 순서

**1. 배포는 됐지만 출시는 안 됐다**

```bash
./scripts/run.sh production flagctl list
show
```

전부 0. 브라우저에서 주문 완료 화면을 열어도 예상 배송일이 없다. 하지만 DB에는 이미 값이 쌓이고 있다.

```bash
./scripts/psql.sh production -c 'SELECT id, user_id, estimated_delivery_date FROM orders ORDER BY id DESC LIMIT 3'
```

**2. 10%에게만 켠다 (배포 없음)**

```bash
./scripts/run.sh production flagctl set show_estimated_delivery on --percent 10
sleep 5; show; show
```

20명 중 몇 명만 1이다. 두 번 실행해도 같은 사용자가 1이다. `bucket`이 사용자 ID의 해시라서 그렇다.
반영까지 최대 5초(`FLAG_CACHE_TTL_SECONDS`)가 걸린다.

**3. 50% → 100%**

```bash
./scripts/run.sh production flagctl set show_estimated_delivery on --percent 50
sleep 5; show
./scripts/run.sh production flagctl set show_estimated_delivery on
sleep 5; show
```

10%에서 1이던 사용자는 50%에서도 1이다. 브라우저를 새로고침하면 초록색 "예상 배송일"이 보인다.

**4. kill switch**

```bash
./scripts/run.sh production flagctl set show_estimated_delivery off
sleep 5; show
```

배포도 롤백도 없이 수 초 만에 전부 0이다. EP6에서 "가장 빠른 되돌리기"로 다시 나온다.

**5. 환경마다 상태가 다르다**

```bash
./scripts/run.sh staging flagctl list
./scripts/run.sh production flagctl list
```

**6. 플래그가 빚이 되지 않게**

```bash
python3 scripts/check_flags.py
python3 scripts/check_flags.py --today 2027-01-15
```

만료일이 지나면 CI의 "Feature flag 검사" step이 실패한다. 오타도 잡는다.

```bash
sed -i.bak 's/"show_estimated_delivery", order/"show_estimated_delivry", order/' app/web.py
python3 scripts/check_flags.py
mv app/web.py.bak app/web.py
```

"코드에서 쓰는데 flags.json에 없다"와 "코드에서 쓰지 않는다"가 함께 나온다.

## 짚을 점

- 플래그가 가리는 것은 화면 표시뿐이다. 새 컬럼에 쓰는 일은 플래그와 무관하게 항상 한다. 그래야 플래그를 켰을 때 보여 줄 데이터가 이미 있다.
- 플래그 저장소(DB)를 읽지 못하면 마지막으로 읽은 값, 그것도 없으면 `flags.json`의 기본값으로 동작한다. `tests/test_flags.py`의 마지막 두 테스트.
- 100%로 켜고 안정되면 플래그를 지우는 PR이 마지막 단계다: `is_enabled` 분기 제거 → `flags.json`에서 삭제 → 테스트 정리. `check_flags.py`가 한쪽만 지운 경우를 잡는다.
- 다음 편을 위해 플래그를 다시 켜 둔다: `./scripts/run.sh production flagctl set show_estimated_delivery on`
