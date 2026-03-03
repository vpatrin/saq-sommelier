from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    name: str | None
    category: str | None
    country: str | None
    color: str | None
    size: str | None
    price: Decimal | None = Field(examples=[24.95])  # For the Swagger example
    availability: bool | None
    rating: float | None
    review_count: int | None
    region: str | None
    appellation: str | None
    designation: str | None
    classification: str | None
    grape: str | None
    alcohol: str | None
    sugar: str | None
    producer: str | None
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
