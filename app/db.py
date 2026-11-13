import psycopg
from psycopg.rows import dict_row


def connect(database_url: str) -> psycopg.Connection:
    # with 블록을 정상 종료하면 commit, 예외가 나면 rollback 한다.
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=3)
