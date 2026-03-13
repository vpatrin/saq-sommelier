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
    url: str | None = None
    online_availability: bool | None
    store_availability: list[str] | None = None
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
    limit: int
    offset: int


class PriceRange(BaseModel):
    min: Decimal
    max: Decimal


class CategoryGroupOut(BaseModel):
    key: str
    label: str
    categories: list[str]


class CategoryFamilyOut(BaseModel):
    key: str
    label: str
    children: list[str]  # group keys


class CountryFacet(BaseModel):
    name: str
    count: int


class FacetsOut(BaseModel):
    categories: list[str]
    grouped_categories: list[CategoryGroupOut]
    category_families: list[CategoryFamilyOut]
    countries: list[CountryFacet]
    regions: list[str]
    grapes: list[str]
    price_range: PriceRange | None
