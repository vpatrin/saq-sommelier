from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.config import MAX_SKU_LENGTH


class TastingIn(BaseModel):
    sku: str = Field(min_length=1, max_length=MAX_SKU_LENGTH)
    rating: int = Field(ge=0, le=100)
    notes: str | None = Field(default=None, max_length=5000)
    pairing: str | None = Field(default=None, max_length=1000)
    tasted_at: date | None = None


class TastingUpdateIn(BaseModel):
    rating: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=5000)
    pairing: str | None = Field(default=None, max_length=1000)
    tasted_at: date | None = None


class TastingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    rating: int
    notes: str | None
    pairing: str | None
    tasted_at: date
    created_at: datetime
    updated_at: datetime
    # Denormalized product fields for the list view — avoids N+1 on the frontend
    product_name: str | None = None
    product_image_url: str | None = None
