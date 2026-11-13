import datetime

import pytest

from app.delivery import estimate_delivery_date

MONDAY = datetime.date(2026, 11, 9)
THURSDAY = datetime.date(2026, 11, 12)
SATURDAY = datetime.date(2026, 11, 14)


@pytest.mark.parametrize(
    ("ordered_on", "shipping_method", "region", "expected"),
    [
        pytest.param(MONDAY, "standard", "metro", datetime.date(2026, 11, 12), id="standard-metro"),
        pytest.param(MONDAY, "standard", "remote", datetime.date(2026, 11, 14), id="remote"),
        pytest.param(MONDAY, "express", "metro", datetime.date(2026, 11, 10), id="express-metro"),
        pytest.param(THURSDAY, "standard", "metro", datetime.date(2026, 11, 16), id="skips-sunday"),
        pytest.param(SATURDAY, "express", "metro", datetime.date(2026, 11, 16), id="sunday-2"),
    ],
)
def test_estimate_delivery_date(ordered_on, shipping_method, region, expected):
    assert estimate_delivery_date(ordered_on, shipping_method, region) == expected
