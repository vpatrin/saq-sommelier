from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.config import MAX_ACK_BATCH_SIZE, MAX_SKU_LENGTH, MAX_USER_ID_LENGTH
from backend.schemas.product import ProductResponse


# input validation for POST /watches
class WatchCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=MAX_USER_ID_LENGTH)
    sku: str = Field(min_length=1, max_length=MAX_SKU_LENGTH)


# Output resource validation for a single watch
class WatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    sku: str
    created_at: datetime


# Wraps a WatchResponse + the joined ProductResponse
class WatchWithProduct(BaseModel):
    """Watch with embedded product info — for the GET /watches list."""

    watch: WatchResponse
    product: ProductResponse | None


class PendingNotification(BaseModel):
    """One user×event pair — the bot sends one Telegram message per item."""

    event_id: int
    sku: str
    user_id: str
    product_name: str | None
    detected_at: datetime


class AckRequest(BaseModel):
    event_ids: list[int] = Field(min_length=1, max_length=MAX_ACK_BATCH_SIZE)
