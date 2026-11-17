"""환경 변수에서 설정을 읽는다.

코드와 이미지는 모든 환경에서 같다.
환경마다 달라지는 값은 전부 여기를 거쳐 들어온다.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

VALID_ENVS = ("dev", "staging", "production")
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    # 환경마다 다른 값.
    app_env: str
    database_url: str
    log_level: str
    payment_api_url: str
    flag_cache_ttl_seconds: float
    # 빌드할 때 이미지에 박히는 값.
    app_version: str
    # 배포할 때 붙는 값 (blue / green).
    app_color: str


def load_settings(environ: Mapping[str, str] = os.environ) -> Settings:
    errors: list[str] = []

    def required(name: str) -> str:
        value = environ.get(name, "").strip()
        if not value:
            errors.append(f"{name}: 값이 없다")
        return value

    app_env = required("APP_ENV")
    if app_env and app_env not in VALID_ENVS:
        errors.append(f"APP_ENV: {app_env!r}는 {VALID_ENVS} 중 하나가 아니다")

    database_url = required("DATABASE_URL")
    payment_api_url = required("PAYMENT_API_URL")

    log_level = environ.get("LOG_LEVEL", "INFO").upper()
    if log_level not in VALID_LOG_LEVELS:
        errors.append(f"LOG_LEVEL: {log_level!r}는 {VALID_LOG_LEVELS} 중 하나가 아니다")

    ttl_raw = environ.get("FLAG_CACHE_TTL_SECONDS", "5")
    try:
        ttl = float(ttl_raw)
    except ValueError:
        ttl = 0.0
        errors.append(f"FLAG_CACHE_TTL_SECONDS: {ttl_raw!r}는 숫자가 아니다")

    # 설정이 잘못됐으면 요청을 받기 전에, 시작할 때 죽는다.
    # 빠진 값을 한 번에 다 알려 준다.
    if errors:
        raise ConfigError("설정 오류:\n  - " + "\n  - ".join(errors))

    return Settings(
        app_env=app_env,
        database_url=database_url,
        log_level=log_level,
        payment_api_url=payment_api_url,
        flag_cache_ttl_seconds=ttl,
        app_version=environ.get("APP_VERSION", "dev"),
        app_color=environ.get("APP_COLOR", "none"),
    )
