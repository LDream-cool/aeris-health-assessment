from dataclasses import dataclass


@dataclass
class SKU:
    sku_id: str
    price_cents: int
    stock: int
    image: str
    option_values: dict[str, str]


@dataclass
class Product:
    id: str
    name: str
    description: str
    currency: str
    options: dict[str, list[str]]
    skus: list[SKU]


class DomainError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
