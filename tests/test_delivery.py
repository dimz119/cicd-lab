import datetime

import pytest

from app.delivery import estimate_delivery_date

MONDAY = datetime.date(2026, 11, 9)
THURSDAY = datetime.date(2026, 11, 12)
SATURDAY = datetime.date(2026, 11, 14)


@pytest.mark.parametrize(
    ("ordered_on", "shipping_method", "expected"),
    [
        pytest.param(MONDAY, "standard", datetime.date(2026, 11, 12), id="standard-3-days"),
        pytest.param(MONDAY, "express", datetime.date(2026, 11, 10), id="express-next-day"),
        pytest.param(THURSDAY, "standard", datetime.date(2026, 11, 16), id="standard-skips-sunday"),
        pytest.param(SATURDAY, "express", datetime.date(2026, 11, 16), id="express-skips-sunday"),
    ],
)
def test_estimate_delivery_date(ordered_on, shipping_method, expected):
    assert estimate_delivery_date(ordered_on, shipping_method) == expected
