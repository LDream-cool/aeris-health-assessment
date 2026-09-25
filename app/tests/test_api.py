import asyncio
from itertools import product

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

from backend.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app, headers={"Idempotency-Key": "test-key"}) as client:
        yield client


def stock(client, sku_id="tee-blue-s"):
    skus = client.get("/api/products/everyday-tee").json()["skus"]
    return next(sku["stock"] for sku in skus if sku["sku_id"] == sku_id)


def test_product_seed_and_images(client):
    response = client.get("/api/products/everyday-tee")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] and data["description"]
    assert data["currency"] == "USD"
    assert set(data["options"]) == {"colour", "size"}
    skus = data["skus"]
    assert len(skus) >= 6
    assert len({sku["sku_id"] for sku in skus}) == len(skus)
    combinations = {(s["option_values"]["colour"], s["option_values"]["size"]) for s in skus}
    assert len(combinations) == len(skus)
    assert set(product(data["options"]["colour"], data["options"]["size"])) - combinations
    assert ("sand", "L") not in combinations
    assert any(s["stock"] == 0 for s in skus)
    for sku in skus:
        assert type(sku["price_cents"]) is int and sku["price_cents"] > 0
        assert sku["stock"] >= 0
        image = client.get(sku["image"])
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/svg+xml")


def test_missing_product(client):
    response = client.get("/api/products/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


def test_empty_cart(client):
    assert client.get("/api/cart").json() == {
        "items": [], "total_item_count": 0, "total_price_cents": 0, "currency": "USD",
    }


def test_add_and_accumulate_items(client):
    first = client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 2})
    assert first.status_code == 200
    assert first.json()["total_item_count"] == 2
    assert stock(client) == 3
    client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 1},
                headers={"Idempotency-Key": "second"})
    client.post("/api/cart/items", json={"sku_id": "tee-black-s", "quantity": 2},
                headers={"Idempotency-Key": "third"})
    response = client.get("/api/cart")
    assert response.status_code == 200
    cart = response.json()
    assert len(cart["items"]) == 2
    assert cart["total_item_count"] == 5
    assert cart["total_price_cents"] == 3 * 2500 + 2 * 2600
    blue = next(item for item in cart["items"] if item["sku_id"] == "tee-blue-s")
    assert blue["quantity"] == 3
    assert blue["unit_price_cents"] == 2500
    assert blue["line_total_cents"] == 7500
    assert blue["stock"] == stock(client) == 2


@pytest.mark.parametrize("quantity", [0, -1, 1.5, 1.0, True, False, "2", None, [], {}])
def test_invalid_quantity_does_not_mutate_state(client, quantity):
    response = client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": quantity})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_QUANTITY"
    assert stock(client) == 5
    assert client.get("/api/cart").json()["total_item_count"] == 0


@pytest.mark.parametrize("payload", [{}, {"sku_id": "tee-blue-s"},
                                     {"sku_id": "", "quantity": 1},
                                     {"sku_id": "  ", "quantity": 1},
                                     {"sku_id": 1, "quantity": 1}])
def test_invalid_request(client, payload):
    assert client.post("/api/cart/items", json=payload).status_code == 422


@pytest.mark.parametrize("sku_id", ["missing", "tee-sand-l"])
def test_nonexistent_sku(client, sku_id):
    response = client.post("/api/cart/items", json={"sku_id": sku_id, "quantity": 1})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SKU_NOT_FOUND"
    assert client.get("/api/cart").json()["items"] == []


@pytest.mark.parametrize("sku_id,quantity", [("tee-blue-m", 1), ("tee-blue-s", 6)])
def test_insufficient_stock(client, sku_id, quantity):
    before = stock(client, sku_id)
    response = client.post("/api/cart/items", json={"sku_id": sku_id, "quantity": quantity})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    assert stock(client, sku_id) == before
    assert client.get("/api/cart").json()["items"] == []


def test_request_uses_current_stock(client):
    payload = {"sku_id": "tee-blue-s", "quantity": 5}
    assert client.post("/api/cart/items", json=payload).status_code == 200
    before = client.get("/api/cart").json()
    assert client.post("/api/cart/items", json=payload,
                       headers={"Idempotency-Key": "second"}).status_code == 409
    assert stock(client) == 0
    assert client.get("/api/cart").json() == before


@pytest.mark.parametrize("field", ["price_cents", "stock", "unit_price_cents"])
def test_client_cannot_supply_price_or_stock(client, field):
    response = client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 1, field: 999})
    assert response.status_code == 422
    assert stock(client) == 5
    assert client.get("/api/cart").json()["items"] == []


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_vite_cors(client, origin):
    response = client.options("/api/cart/items", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,idempotency-key",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_unknown_origin_not_allowed(client):
    response = client.get("/api/cart", headers={"Origin": "https://unknown.example"})
    assert "access-control-allow-origin" not in response.headers


def test_app_instances_have_independent_state(client):
    client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 1})
    with TestClient(create_app()) as other:
        assert stock(other) == 5
        assert other.get("/api/cart").json()["items"] == []


@pytest.mark.parametrize("key", [None, "", "   ", "x" * 201])
def test_idempotency_header_required(client, key):
    client.headers.pop("Idempotency-Key")
    headers = {} if key is None else {"Idempotency-Key": key}
    response = client.post("/api/cart/items", headers=headers,
                           json={"sku_id": "tee-blue-s", "quantity": 1})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IDEMPOTENCY_KEY"
    assert stock(client) == 5
    assert client.get("/api/cart").json()["total_item_count"] == 0


def test_exact_retry_returns_original_response_after_other_changes(client):
    payload = {"sku_id": "tee-blue-s", "quantity": 2}
    original = client.post("/api/cart/items", json=payload)
    assert original.status_code == 200
    client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 1},
                headers={"Idempotency-Key": "another-operation"})
    before = client.get("/api/cart").json()
    # JSON field order has no effect on the validated request identity.
    replay = client.post("/api/cart/items", json={"quantity": 2, "sku_id": "tee-blue-s"})
    assert replay.status_code == original.status_code
    assert replay.content == original.content
    assert client.get("/api/cart").json() == before
    assert stock(client) == 2


def test_retry_after_consuming_all_stock(client):
    payload = {"sku_id": "tee-black-l", "quantity": 1}
    original = client.post("/api/cart/items", json=payload)
    replay = client.post("/api/cart/items", json=payload)
    assert original.status_code == replay.status_code == 200
    assert original.json() == replay.json()
    assert stock(client, "tee-black-l") == 0
    assert client.get("/api/cart").json()["total_item_count"] == 1


@pytest.mark.parametrize("payload", [
    {"sku_id": "tee-blue-s", "quantity": 2},
    {"sku_id": "tee-black-s", "quantity": 1},
])
def test_idempotency_conflict(client, payload):
    original = client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 1})
    conflict = client.post("/api/cart/items", json=payload)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert stock(client) == 4
    assert stock(client, "tee-black-s") == 2
    assert client.get("/api/cart").json() == original.json()
    assert client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 1}).json() == original.json()


@pytest.mark.parametrize("sku_id,quantity,status", [("missing", 1, 404), ("tee-blue-s", 6, 409)])
def test_business_failure_is_replayed(client, sku_id, quantity, status):
    payload = {"sku_id": sku_id, "quantity": quantity}
    original = client.post("/api/cart/items", json=payload)
    replay = client.post("/api/cart/items", json=payload)
    assert original.status_code == replay.status_code == status
    assert original.content == replay.content
    conflict = client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 1})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert stock(client) == 5
    assert client.get("/api/cart").json()["items"] == []


def test_invalid_request_does_not_consume_key(client):
    assert client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 0}).status_code == 422
    assert client.post("/api/cart/items", json={"sku_id": "tee-blue-s", "quantity": 1}).status_code == 200
    assert stock(client) == 4


def test_unexpected_failure_is_safe_and_does_not_partially_commit(app, monkeypatch):
    shop = app.state.shop
    snapshot = shop._cart_snapshot

    def broken_snapshot(*args):
        raise RuntimeError("sensitive internal exception details")

    monkeypatch.setattr(shop, "_cart_snapshot", broken_snapshot)
    with TestClient(app, raise_server_exceptions=False) as client:
        headers = {"Idempotency-Key": "retry-me", "Origin": "http://localhost:5173"}
        payload = {"sku_id": "tee-blue-s", "quantity": 1}
        response = client.post("/api/cart/items", json=payload, headers=headers)
        assert response.status_code == 500
        assert response.json() == {"error": {
            "code": "INTERNAL_ERROR", "message": "An unexpected server error occurred.",
        }}
        assert "sensitive" not in response.text and "Traceback" not in response.text
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert shop.store.skus["tee-blue-s"].stock == 5
        assert shop.store.cart == {}
        assert shop.store.idempotency == {}
        monkeypatch.setattr(shop, "_cart_snapshot", snapshot)
        assert client.post("/api/cart/items", json=payload, headers=headers).status_code == 200


def test_routing_error_uses_error_contract(client):
    response = client.get("/api/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_ERROR"


async def competing_requests(app, monkeypatch, keys):
    shop = app.state.shop
    original_add = shop.add_item
    both_arrived = asyncio.Event()
    arrivals = 0

    async def observed_add(*args):
        nonlocal arrivals
        arrivals += 1
        if arrivals == 2:
            both_arrived.set()
        # Observe arrival only; all validation and mutation use real code.
        return await original_add(*args)

    monkeypatch.setattr(shop, "add_item", observed_add)
    assert shop.store.skus["tee-black-l"].stock == 1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Queue both real HTTP requests behind the same lock before releasing it.
        async with shop.store.lock:
            tasks = [asyncio.create_task(client.post(
                "/api/cart/items", headers={"Idempotency-Key": key},
                json={"sku_id": "tee-black-l", "quantity": 1},
            )) for key in keys]
            await asyncio.wait_for(both_arrived.wait(), timeout=5)
            assert all(not task.done() for task in tasks)
        responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
        assert shop.store.skus["tee-black-l"].stock == 0
        cart = (await client.get("/api/cart")).json()
        assert cart["total_item_count"] == 1
        assert len(cart["items"]) == 1
        assert cart["items"][0]["quantity"] == 1
        return responses


def test_concurrent_final_unit(app, monkeypatch):
    responses = asyncio.run(competing_requests(app, monkeypatch, ["first", "second"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    failure = next(response for response in responses if response.status_code == 409)
    assert failure.json()["error"]["code"] == "INSUFFICIENT_STOCK"


def test_concurrent_same_key_reserves_only_once(app, monkeypatch):
    responses = asyncio.run(competing_requests(app, monkeypatch, ["same", "same"]))
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].content == responses[1].content
