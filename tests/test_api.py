import datetime

import psycopg
import pytest

pytestmark = pytest.mark.integration

ORDER = {"user_id": "user-1", "book_title": "파이프라인 설계 입문", "quantity": 2}


def test_health_endpoints(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_info_exposes_environment_but_not_secrets(client, settings):
    body = client.get("/info").get_json()

    assert body["env"] == "dev"
    assert body["version"] == "test"
    assert settings.database_url not in str(body)


def test_every_response_says_which_version_served_it(client):
    response = client.get("/healthz")

    assert response.headers["X-App-Version"] == "test"
    assert response.headers["X-App-Color"] == "none"


def test_create_and_read_order(client):
    created = client.post("/orders", json=ORDER)
    assert created.status_code == 201
    order = created.get_json()
    assert order["shipping_method"] == "standard"

    fetched = client.get(f"/orders/{order['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json() == order


def test_form_order_redirects_to_complete_page(client):
    response = client.post("/orders", data=ORDER)

    assert response.status_code == 303
    page = client.get(response.headers["Location"])
    assert page.status_code == 200
    assert "주문이 완료되었습니다" in page.get_data(as_text=True)


@pytest.mark.parametrize(
    "override",
    [
        {"user_id": ""},
        {"book_title": " "},
        {"quantity": 0},
        {"quantity": "many"},
        {"shipping_method": "drone"},
    ],
)
def test_rejects_invalid_order(client, override):
    response = client.post("/orders", json={**ORDER, **override})

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_unknown_order_is_404(client):
    assert client.get("/orders/999").status_code == 404
    assert client.get("/orders/999/complete").status_code == 404


def set_flag(settings, enabled: bool, percent: int = 100) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO feature_flags (name, enabled, rollout_percent)
            VALUES ('show_estimated_delivery', %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET enabled = EXCLUDED.enabled, rollout_percent = EXCLUDED.rollout_percent
            """,
            (enabled, percent),
        )


def test_new_order_stores_estimated_delivery_date(client):
    order = client.post("/orders", json=ORDER).get_json()

    delivery = datetime.date.fromisoformat(order["estimated_delivery_date"])
    assert delivery > datetime.date.today()


def test_complete_page_hides_delivery_date_while_flag_is_off(client):
    order = client.post("/orders", json=ORDER).get_json()

    page = client.get(f"/orders/{order['id']}/complete").get_data(as_text=True)

    assert "예상 배송일" not in page


def test_complete_page_shows_delivery_date_when_flag_is_on(client, settings):
    order = client.post("/orders", json=ORDER).get_json()
    set_flag(settings, enabled=True)

    page = client.get(f"/orders/{order['id']}/complete").get_data(as_text=True)

    assert "예상 배송일" in page


def test_flag_can_be_turned_off_again_without_deploy(client, settings):
    order = client.post("/orders", json=ORDER).get_json()
    set_flag(settings, enabled=True)
    set_flag(settings, enabled=False)

    page = client.get(f"/orders/{order['id']}/complete").get_data(as_text=True)

    assert "예상 배송일" not in page


def test_insert_without_delivery_date_is_rejected_after_contract(settings, client):
    # 컬럼을 모르는 옛 버전(v1.0.0)은 estimated_delivery_date 없이 INSERT 한다.
    # contract 뒤에는 그 버전으로 롤백할 수 없다는 뜻이다.
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.NotNullViolation):
            conn.execute(
                "INSERT INTO orders (user_id, book_title, quantity) "
                "VALUES ('old-user', '옛 주문', 1)"
            )
