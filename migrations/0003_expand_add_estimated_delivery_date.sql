-- expand: 예상 배송일 컬럼을 추가한다.
--
-- NULL을 허용하고 DEFAULT를 두지 않는다.
-- 그래서 이 컬럼을 모르는 옛 버전의 INSERT도 계속 성공한다.
-- 기존 행을 다시 쓰지 않으므로 테이블이 커도 순식간에 끝난다.

-- 긴 트랜잭션이 테이블을 잡고 있으면 기다리지 않고 실패한다.
-- 실패하면 다시 시도하면 된다. 줄 서서 기다리면 뒤의 모든 쿼리가 함께 멈춘다.
SET LOCAL lock_timeout = '5s';

ALTER TABLE orders ADD COLUMN estimated_delivery_date DATE;
