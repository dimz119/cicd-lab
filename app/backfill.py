"""기존 주문의 estimated_delivery_date를 채운다 (backfill).

python -m app.backfill
python -m app.backfill --batch-size 500 --sleep 0.2

UPDATE 한 번으로 전부 바꾸지 않는다.
조금씩 나눠 바꾸고 배치마다 commit 해서 잠금을 짧게 잡는다.
중간에 멈춰도 다시 실행하면 남은 행부터 이어서 한다.
"""

import argparse
import sys
import time

import psycopg

from app.config import load_settings
from app.delivery import estimate_delivery_date


def backfill(database_url: str, *, batch_size: int = 1000, sleep: float = 0.0, out=print) -> int:
    total = 0
    with psycopg.connect(database_url) as conn:
        while True:
            # SKIP LOCKED: 지금 다른 요청이 쓰고 있는 행은 건너뛰고 다음 배치에서 다시 본다.
            rows = conn.execute(
                """
                SELECT id, created_at, shipping_method
                FROM orders
                WHERE estimated_delivery_date IS NULL
                ORDER BY id
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (batch_size,),
            ).fetchall()
            if not rows:
                conn.commit()
                break

            # 새 주문에 쓰는 계산 함수를 그대로 쓴다.
            # 그래야 backfill한 값과 새로 쓰는 값이 같은 규칙을 따른다.
            updates = [
                (estimate_delivery_date(created_at.date(), shipping_method), order_id)
                for order_id, created_at, shipping_method in rows
            ]
            with conn.cursor() as cursor:
                cursor.executemany(
                    "UPDATE orders SET estimated_delivery_date = %s WHERE id = %s",
                    updates,
                )
            conn.commit()

            total += len(rows)
            out(f"  {total}건 완료 (마지막 id={rows[-1][0]})")
            # 배치 사이에 쉬어서 운영 트래픽에 자리를 내준다.
            time.sleep(sleep)

        remaining = conn.execute(
            "SELECT count(*) FROM orders WHERE estimated_delivery_date IS NULL"
        ).fetchone()[0]
    out(f"backfill 끝: {total}건 채움, NULL {remaining}건 남음")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backfill")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--sleep", type=float, default=0.1)
    args = parser.parse_args(argv)

    backfill(load_settings().database_url, batch_size=args.batch_size, sleep=args.sleep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
