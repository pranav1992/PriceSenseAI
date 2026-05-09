import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.database import Base, engine
from .core.exception_handlers import register_exception_handlers
from .core.logging import configure_logging
from .core.middleware import RequestTracingMiddleware
from .models import competitor, product  # noqa: F401 — registers models with Base
from .routes.analysis import router as analysis_router
from .routes.competitors import router as competitors_router
from .routes.health import router as health_router
from .routes.products import router as products_router

_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]


def create_app() -> FastAPI:
    configure_logging()
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestTracingMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(products_router, prefix="/api/products", tags=["products"])
    app.include_router(competitors_router, prefix="/api/competitors", tags=["competitors"])
    app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])
    return app


app = create_app()
