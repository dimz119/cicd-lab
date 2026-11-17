import pytest

from app.config import ConfigError, load_settings

VALID = {
    "APP_ENV": "staging",
    "DATABASE_URL": "postgresql://orders:pw@db:5432/orders",
    "PAYMENT_API_URL": "https://sandbox.pay.example.com",
}


def test_loads_valid_settings_with_defaults():
    settings = load_settings(VALID)

    assert settings.app_env == "staging"
    assert settings.log_level == "INFO"
    assert settings.flag_cache_ttl_seconds == 5
    assert settings.app_version == "dev"


def test_reports_every_missing_value_at_once():
    with pytest.raises(ConfigError) as error:
        load_settings({})

    message = str(error.value)
    assert "APP_ENV" in message
    assert "DATABASE_URL" in message
    assert "PAYMENT_API_URL" in message


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_ENV", "prod"),
        ("LOG_LEVEL", "VERBOSE"),
        ("FLAG_CACHE_TTL_SECONDS", "soon"),
    ],
)
def test_rejects_invalid_value(name, value):
    with pytest.raises(ConfigError, match=name):
        load_settings({**VALID, name: value})
