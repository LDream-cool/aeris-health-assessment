from copy import deepcopy

from .domain import DomainError, Product
from .store import IdempotencyRecord, InMemoryStore


class ShopService:
    def __init__(self, store: InMemoryStore):
        self.store = store

    async def get_product(self, product_id: str) -> Product:
        async with self.store.lock:
            product = self.store.products.get(product_id)
            if product is None:
                raise DomainError("PRODUCT_NOT_FOUND", "Product not found.")
            return deepcopy(product)

    async def add_item(self, sku_id: str, quantity: int, idempotency_key: str) -> dict:
        if type(quantity) is not int or quantity <= 0:
            raise DomainError("INVALID_QUANTITY", "Quantity must be a positive integer.")
        payload = (sku_id, quantity)
        async with self.store.lock:
            previous = self.store.idempotency.get(idempotency_key)
            if previous is not None:
                if previous.payload != payload:
                    raise DomainError("IDEMPOTENCY_CONFLICT", "Key was already used with a different payload.")
                if previous.error is not None:
                    raise DomainError(*previous.error)
                return deepcopy(previous.result)

            try:
                sku = self.store.skus.get(sku_id)
                if sku is None:
                    raise DomainError("SKU_NOT_FOUND", "SKU not found.")
                if quantity > sku.stock:
                    raise DomainError("INSUFFICIENT_STOCK", "Requested quantity exceeds current stock.")
            except DomainError as error:
                # Valid business failures are replayed; malformed requests never
                # reach this point. Unexpected failures are not cached.
                self.store.idempotency[idempotency_key] = IdempotencyRecord(
                    payload, error=(error.code, str(error)),
                )
                raise

            # Prepare the response before committing so a snapshot failure cannot
            # leave inventory changed without a saved idempotency result.
            updated_cart = dict(self.store.cart)
            updated_cart[sku_id] = updated_cart.get(sku_id, 0) + quantity
            result = self._cart_snapshot(updated_cart)
            for item in result["items"]:
                if item["sku_id"] == sku_id:
                    item["stock"] -= quantity
            record = IdempotencyRecord(payload, result=deepcopy(result))

            # No awaits between these writes: the entire commit holds the lock.
            sku.stock -= quantity
            self.store.cart = updated_cart
            self.store.idempotency[idempotency_key] = record
            return result

    async def get_cart(self) -> dict:
        async with self.store.lock:
            return self._cart_snapshot()

    def _cart_snapshot(self, cart: dict[str, int] | None = None) -> dict:
        # Called while holding the lock; return detached data, never live state.
        items = []
        for sku_id, quantity in sorted((self.store.cart if cart is None else cart).items()):
            sku = self.store.skus[sku_id]
            items.append({
                "sku_id": sku_id,
                "quantity": quantity,
                "unit_price_cents": sku.price_cents,
                "line_total_cents": quantity * sku.price_cents,
                "stock": sku.stock,
                "image": sku.image,
                "option_values": dict(sku.option_values),
            })
        return {
            "items": items,
            "total_item_count": sum(item["quantity"] for item in items),
            "total_price_cents": sum(item["line_total_cents"] for item in items),
            "currency": "USD",
        }
