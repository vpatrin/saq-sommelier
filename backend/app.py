from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.admin import router as admin_router
from backend.api.auth import router as auth_router
from backend.api.chat import router as chat_router
from backend.api.health import router as health_router
from backend.api.products import router as products_router
from backend.api.recommendations import router as recommendations_router
from backend.api.stores import router as stores_router
from backend.api.tastings import router as tastings_router
from backend.api.users import router as users_router
from backend.api.waitlist import router as waitlist_router
from backend.api.watches import router as watches_router
from backend.auth import verify_admin, verify_auth
from backend.config import SERVICE_NAME, backend_settings
from backend.db import SessionLocal, engine, verify_db_connection
from backend.errors import register_exception_handlers
from backend.rate_limit import limiter
from backend.repositories import users as users_repo
from core.config.settings import settings
from core.logging import setup_logging

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
        if not backend_settings.GITHUB_CLIENT_ID:
            raise RuntimeError("GITHUB_CLIENT_ID must be set in production")
        if not backend_settings.GITHUB_CLIENT_SECRET:
            raise RuntimeError("GITHUB_CLIENT_SECRET must be set in production")
        if not backend_settings.GOOGLE_CLIENT_ID:
            raise RuntimeError("GOOGLE_CLIENT_ID must be set in production")
        if not backend_settings.GOOGLE_CLIENT_SECRET:
            raise RuntimeError("GOOGLE_CLIENT_SECRET must be set in production")
        if not backend_settings.FRONTEND_URL:
            raise RuntimeError("FRONTEND_URL must be set in production")
        if not backend_settings.BACKEND_URL:
            raise RuntimeError("BACKEND_URL must be set in production")
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


app = FastAPI(title="Coupette", version="1.0.0", debug=settings.DEBUG, lifespan=lifespan)
app.state.limiter = limiter

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=backend_settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded"},
    )


register_exception_handlers(app)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
app.include_router(health_router)
app.include_router(auth_router, prefix="/api")
app.include_router(waitlist_router, prefix="/api")  # public — no auth
app.include_router(products_router, prefix="/api", dependencies=_auth)
app.include_router(stores_router, prefix="/api", dependencies=_auth)
app.include_router(watches_router, prefix="/api", dependencies=_auth)
app.include_router(tastings_router, prefix="/api", dependencies=_auth)
app.include_router(recommendations_router, prefix="/api", dependencies=_auth)
app.include_router(chat_router, prefix="/api", dependencies=_auth)
app.include_router(users_router, prefix="/api", dependencies=_auth)
app.include_router(admin_router, prefix="/api", dependencies=[Depends(verify_admin)])
