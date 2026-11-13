-- contract: 예상 배송일을 NOT NULL로 바꾼다.
--
-- 적용 전에 확인할 것:
--   1. 이 컬럼에 쓰지 않는 버전(v1.0.0)이 어느 환경에도 떠 있지 않다.
--   2. backfill이 끝나 NULL인 행이 없다.
-- 적용한 뒤에는 v1.0.0으로 롤백할 수 없다. 그 버전의 INSERT가 거부된다.

SET LOCAL lock_timeout = '5s';

-- SET NOT NULL을 바로 실행하면 테이블 전체를 읽는 동안 강한 잠금을 잡는다.
-- 그래서 세 단계로 나눈다.

-- 1. 검증하지 않는 CHECK 제약을 건다. 새로 쓰는 행에만 적용되고 즉시 끝난다.
ALTER TABLE orders
    ADD CONSTRAINT orders_estimated_delivery_date_not_null
    CHECK (estimated_delivery_date IS NOT NULL) NOT VALID;

-- 2. 기존 행을 검증한다. 읽기와 쓰기를 막지 않는다.
--    NULL이 남아 있으면 여기서 실패하고 전체가 취소된다.
ALTER TABLE orders VALIDATE CONSTRAINT orders_estimated_delivery_date_not_null;

-- 3. 검증된 CHECK가 있으면 SET NOT NULL은 테이블을 다시 읽지 않는다.
ALTER TABLE orders ALTER COLUMN estimated_delivery_date SET NOT NULL;
ALTER TABLE orders DROP CONSTRAINT orders_estimated_delivery_date_not_null;
