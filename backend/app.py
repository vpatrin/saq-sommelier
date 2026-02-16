from core.config.settings import settings
from core.logging import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.health import router as health_router
from backend.api.products import router as products_router
from backend.config import SERVICE_NAME
from backend.errors import register_exception_handlers

setup_logging(SERVICE_NAME)

app = FastAPI(title="SAQ Sommelier", version="0.1.0", debug=settings.DEBUG)

# CORS — explicit allowlist, no wildcards.
# Add "https://wine.victorpatrin.dev" when frontend ships.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=[],
)

register_exception_handlers(app)
app.include_router(health_router)
app.include_router(products_router, prefix="/api/v1")
