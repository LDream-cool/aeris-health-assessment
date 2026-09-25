from .domain import Product, SKU
from .store import InMemoryStore


def create_seeded_store() -> InMemoryStore:
    variants = [
        ("blue", "S", 2500, 5),
        ("blue", "M", 2500, 0),
        ("blue", "L", 2700, 3),
        ("black", "S", 2600, 2),
        ("black", "M", 2600, 8),
        ("black", "L", 2800, 1),
        ("sand", "S", 2500, 4),
        ("sand", "M", 2500, 6),
    ]
    # Sand/L is unavailable (no SKU); Blue/M exists but is out of stock.
    product = Product(
        id="everyday-tee",
        name="Everyday Cotton Tee",
        description="A soft cotton T-shirt with a relaxed fit for everyday wear.",
        currency="USD",
        options={"colour": ["blue", "black", "sand"], "size": ["S", "M", "L"]},
        skus=[SKU(
            sku_id=f"tee-{colour}-{size.lower()}",
            price_cents=price,
            stock=stock,
            image=f"/static/tee-{colour}.svg",
            option_values={"colour": colour, "size": size},
        ) for colour, size, price, stock in variants],
    )
    return InMemoryStore([product])
