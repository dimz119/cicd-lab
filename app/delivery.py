"""예상 배송일 계산."""

import datetime

# 배송 방법별로 주문일에서 며칠 뒤에 도착하는지.
LEAD_DAYS = {
    "standard": 3,
    "express": 1,
}

SUNDAY = 6


def estimate_delivery_date(ordered_on: datetime.date, shipping_method: str) -> datetime.date:
    delivery = ordered_on + datetime.timedelta(days=LEAD_DAYS[shipping_method])
    # 일요일에는 배송하지 않는다.
    if delivery.weekday() == SUNDAY:
        delivery += datetime.timedelta(days=1)
    return delivery
