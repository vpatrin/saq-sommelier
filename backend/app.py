from core.logging import setup_logging
from fastapi import FastAPI

from backend.api.health import router as health_router
from backend.api.products import router as products_router
from backend.config import SERVICE_NAME

setup_logging(SERVICE_NAME)

app = FastAPI(title="SAQ Sommelier", version="0.1.0")
app.include_router(health_router)
app.include_router(products_router, prefix="/api/v1")
