"""orders 테이블 접근.

SELECT * 를 쓰지 않고 컬럼을 하나씩 적는다.
그래야 스키마에 컬럼이 늘거나 줄어도 이 버전의 코드가 영향을 받지 않는다.
"""

import datetime

import psycopg

ORDER_COLUMNS = (
    "id, user_id, book_title, quantity, shipping_method, created_at, estimated_delivery_date"
)


def create_order(
    conn: psycopg.Connection,
    *,
    user_id: str,
    book_title: str,
    quantity: int,
    shipping_method: str,
    estimated_delivery_date: datetime.date,
) -> dict:
    return conn.execute(
        f"""
        INSERT INTO orders
            (user_id, book_title, quantity, shipping_method, estimated_delivery_date)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING {ORDER_COLUMNS}
        """,
        (user_id, book_title, quantity, shipping_method, estimated_delivery_date),
    ).fetchone()


def get_order(conn: psycopg.Connection, order_id: int) -> dict | None:
    return conn.execute(
        f"SELECT {ORDER_COLUMNS} FROM orders WHERE id = %s",
        (order_id,),
    ).fetchone()


def fetch_flag_states(conn: psycopg.Connection) -> dict[str, tuple[bool, int]]:
    rows = conn.execute("SELECT name, enabled, rollout_percent FROM feature_flags").fetchall()
    return {row["name"]: (row["enabled"], row["rollout_percent"]) for row in rows}
