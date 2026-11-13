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
