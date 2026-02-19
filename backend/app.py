from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from core.config.settings import settings
from core.logging import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.api.health import router as health_router
from backend.api.products import router as products_router
from backend.api.watches import router as watches_router
from backend.config import SERVICE_NAME, backend_settings
from backend.db import engine, verify_db_connection
from backend.errors import register_exception_handlers

setup_logging(SERVICE_NAME, level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await verify_db_connection()
    logger.info("Database connection verified")
    yield  # When uvicorn shuts down, it runs the code after yield
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(title="SAQ Sommelier", version="1.0.0", debug=settings.DEBUG, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=backend_settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

register_exception_handlers(app)
app.include_router(health_router)
app.include_router(products_router, prefix="/api/v1")
app.include_router(watches_router, prefix="/api/v1")
