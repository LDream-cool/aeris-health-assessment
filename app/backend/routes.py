from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from .schemas import AddCartItem, CartResponse, ProductResponse
from .service import ShopService


router = APIRouter(prefix="/api")


async def get_service(request: Request) -> ShopService:
    return request.app.state.shop


Service = Annotated[ShopService, Depends(get_service)]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, service: Service):
    return await service.get_product(product_id)


@router.post("/cart/items", response_model=CartResponse)
async def add_cart_item(
    item: AddCartItem,
    service: Service,
    idempotency_key: Annotated[str, Header(
        alias="Idempotency-Key", min_length=1, max_length=200, pattern=r"^[!-~]+$",
    )],
):
    return await service.add_item(item.sku_id, item.quantity, idempotency_key)


@router.get("/cart", response_model=CartResponse)
async def get_cart(service: Service):
    return await service.get_cart()
