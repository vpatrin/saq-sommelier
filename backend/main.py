from fastapi import Depends, FastAPI
from shared.logging import setup_logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.products import router as products_router
from backend.config import SERVICE_NAME
from backend.db import get_db

setup_logging(SERVICE_NAME)

app = FastAPI(title="SAQ Sommelier", version="0.1.0")
app.include_router(products_router)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Health check — verifies the API is up and the database is reachable."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
