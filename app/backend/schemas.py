from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AddCartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: Annotated[str, Field(strict=True, min_length=1, pattern=r"^\S+$")]
    quantity: Annotated[int, Field(strict=True, gt=0)]


class SKUResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str
    price_cents: int
    stock: int
    image: str
    option_values: dict[str, str]


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    currency: str
    options: dict[str, list[str]]
    skus: list[SKUResponse]


class CartItemResponse(BaseModel):
    sku_id: str
    quantity: int
    unit_price_cents: int
    line_total_cents: int
    stock: int
    image: str
    option_values: dict[str, str]


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_item_count: int
    total_price_cents: int
    currency: str
