from pathlib import Path
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .domain import DomainError
from .routes import router
from .seed import create_seeded_store
from .service import ShopService


logger = logging.getLogger(__name__)


def error_response(status: int, code: str, message: str, details=None, headers=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status, content={"error": error}, headers=headers)


def create_app() -> FastAPI:
    app = FastAPI(title="Aeris Variant Store", version="0.1.0")
    # A fresh store per app instance keeps tests isolated and seeds every startup.
    app.state.shop = ShopService(create_seeded_store())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        status = {"PRODUCT_NOT_FOUND": 404, "SKU_NOT_FOUND": 404,
                  "INVALID_QUANTITY": 422, "INSUFFICIENT_STOCK": 409,
                  "IDEMPOTENCY_CONFLICT": 409}[error.code]
        return error_response(status, error.code, str(error))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        errors = error.errors()
        if any(item["loc"] == ("body", "quantity") for item in errors):
            code, message = "INVALID_QUANTITY", "Quantity must be a positive integer."
        elif any(item["loc"] == ("header", "Idempotency-Key") for item in errors):
            code, message = "INVALID_IDEMPOTENCY_KEY", "A nonempty Idempotency-Key header is required (up to 200 visible ASCII characters)."
        else:
            code, message = "INVALID_REQUEST", "Request validation failed."
        return error_response(422, code, message, details=[
            {"field": list(item["loc"]), "message": item["msg"]} for item in errors
        ])

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return error_response(error.status_code, "HTTP_ERROR", str(error.detail), headers=error.headers)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception):
        logger.error("Unhandled API error", exc_info=(type(error), error, error.__traceback__))
        response = error_response(500, "INTERNAL_ERROR", "An unexpected server error occurred.")
        # The server-error handler runs outside CORSMiddleware. Preserve CORS
        # here so the frontend can read the safe error body as well.
        origin = request.headers.get("origin")
        if origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    return app


app = create_app()
