from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.config import MAX_ACK_BATCH_SIZE, MAX_SKU_LENGTH, MAX_USER_ID_LENGTH
from backend.schemas.product import ProductOut


# input validation for POST /watches
class WatchIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=MAX_USER_ID_LENGTH)
    sku: str = Field(min_length=1, max_length=MAX_SKU_LENGTH)


# Output resource validation for a single watch
class WatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    sku: str
    created_at: datetime


# Wraps a WatchOut + the joined ProductOut
class WatchWithProduct(BaseModel):
    """Watch with embedded product info — for the GET /watches list."""

    watch: WatchOut
    product: ProductOut | None


class NotificationOut(BaseModel):
    """One user×event pair — grouped by (user, sku) on the bot side for sending."""

    event_id: int
    sku: str
    user_id: str
    available: bool
    product_name: str | None
    detected_at: datetime
    # NULL = online event, non-NULL = in-store event
    saq_store_id: str | None = None
    store_name: str | None = None
    # Current online availability from products table (independent of event type)
    online_available: bool | None = None
    # True when the product was removed from SAQ's catalog (delisted_at is set on Product)
    delisted: bool = False


class AckIn(BaseModel):
    event_ids: list[int] = Field(min_length=1, max_length=MAX_ACK_BATCH_SIZE)
