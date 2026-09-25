from asyncio import Lock
from dataclasses import dataclass

from .domain import Product


@dataclass(frozen=True)
class IdempotencyRecord:
    payload: tuple[str, int]
    result: dict | None = None
    error: tuple[str, str] | None = None


class InMemoryStore:
    """One shared cart per process; restart resets all state.

    Use a single server worker. The lock protects both inventory and cart so
    checking stock and reserving units is one operation within this process.
    Access this store from one event loop. Keys are retained until restart;
    another process would have independent inventory and idempotency records.
    """

    def __init__(self, products: list[Product]):
        self.products = {product.id: product for product in products}
        self.skus = {sku.sku_id: sku for product in products for sku in product.skus}
        self.cart: dict[str, int] = {}
        self.idempotency: dict[str, IdempotencyRecord] = {}
        self.lock = Lock()
