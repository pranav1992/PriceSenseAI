from fastapi import FastAPI

from .core.exception_handlers import register_exception_handlers
from .core.middleware import RequestIdMiddleware
from .routes.health import router as health_router
from .routes.products import router as products_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(products_router, prefix="/api/products", tags=["products"])
    return app


app = create_app()
