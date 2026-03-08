from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    name: str | None
    category: str | None
    country: str | None
    size: str | None
    price: Decimal | None = Field(examples=[24.95])  # For the Swagger example
    online_availability: bool | None
    rating: float | None
    review_count: int | None
    region: str | None
    appellation: str | None
    designation: str | None
    classification: str | None
    grape: str | None
    grape_blend: list[dict[str, Any]] | None = None
    alcohol: str | None
    sugar: str | None
    producer: str | None
    vintage: str | None = None
    taste_tag: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedOut(BaseModel):
    products: list[ProductOut]
    total: int
    page: int
    per_page: int
    pages: int


class PriceRange(BaseModel):
    min: Decimal
    max: Decimal


class FacetsOut(BaseModel):
    categories: list[str]
    countries: list[str]
    regions: list[str]
    grapes: list[str]
    price_range: PriceRange | None
