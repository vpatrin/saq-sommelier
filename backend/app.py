from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from core.config.settings import settings
from core.logging import setup_logging
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.api.admin import router as admin_router
from backend.api.auth import router as auth_router
from backend.api.health import router as health_router
from backend.api.products import router as products_router
from backend.api.recommendations import router as recommendations_router
from backend.api.stores import stores_router, users_router
from backend.api.watches import router as watches_router
from backend.auth import verify_admin, verify_auth
from backend.config import SERVICE_NAME, backend_settings
from backend.db import SessionLocal, engine, verify_db_connection
from backend.errors import register_exception_handlers
from backend.repositories import users as users_repo

setup_logging(SERVICE_NAME, level=settings.LOG_LEVEL)

_auth = [Depends(verify_auth)]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if settings.ENVIRONMENT == "production":
        if not backend_settings.BOT_SECRET:
            raise RuntimeError("BOT_SECRET must be set in production")
        if not backend_settings.JWT_SECRET_KEY:
            raise RuntimeError("JWT_SECRET_KEY must be set in production")
        if not backend_settings.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN must be set in production")
    await verify_db_connection()
    logger.info("Database connection verified")

    if not backend_settings.ADMIN_TELEGRAM_ID:
        raise RuntimeError("ADMIN_TELEGRAM_ID must be set. Run: make create-admin")
    async with SessionLocal() as db:
        admin = await users_repo.find_active_admin(db, backend_settings.ADMIN_TELEGRAM_ID)
    if not admin:
        raise RuntimeError(
            f"No active admin with telegram_id={backend_settings.ADMIN_TELEGRAM_ID}. "
            "Run: make create-admin"
        )
    logger.info("Admin user verified")

    yield  # When uvicorn shuts down, it runs the code after yield
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(title="SAQ Sommelier", version="1.0.0", debug=settings.DEBUG, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=backend_settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

register_exception_handlers(app)
app.include_router(health_router)
app.include_router(auth_router, prefix="/api")
app.include_router(products_router, prefix="/api", dependencies=_auth)
app.include_router(stores_router, prefix="/api", dependencies=_auth)
app.include_router(users_router, prefix="/api", dependencies=_auth)
app.include_router(watches_router, prefix="/api", dependencies=_auth)
app.include_router(recommendations_router, prefix="/api", dependencies=_auth)
app.include_router(admin_router, prefix="/api", dependencies=[Depends(verify_admin)])
