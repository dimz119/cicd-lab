import os

import psycopg
import pytest

from app import migrate
from app.config import Settings
from app.web import create_app


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        # CI에서는 DB가 없다고 조용히 건너뛰면 안 된다.
        if os.environ.get("REQUIRE_DB") == "1":
            pytest.fail("REQUIRE_DB=1 인데 TEST_DATABASE_URL이 없다")
        pytest.skip("TEST_DATABASE_URL이 없어 통합 테스트를 건너뛴다")

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    # 테스트 DB는 마이그레이션 파일로 만든다.
    # 그래서 테스트가 통과하면 마이그레이션도 검증된 것이다.
    migrate.up(url, allow_contract=True, out=lambda _: None)
    return url


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(
        app_env="dev",
        database_url=database_url,
        log_level="WARNING",
        payment_api_url="https://sandbox.pay.example.com",
        flag_cache_ttl_seconds=0,
        app_version="test",
        app_color="none",
    )


@pytest.fixture
def client(settings: Settings):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE orders, feature_flags RESTART IDENTITY")
    return create_app(settings).test_client()
