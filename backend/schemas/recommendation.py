from decimal import Decimal

from pydantic import BaseModel, Field

from backend.config import MAX_SEARCH_LENGTH
from backend.schemas.product import ProductOut


class IntentResult(BaseModel):
    """Structured filters extracted from a natural language wine query."""

    categories: list[str] = []
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    country: str | None = None
    available_only: bool = True
    semantic_query: str = ""
    exclude_grapes: list[str] = []


class RecommendationIn(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_SEARCH_LENGTH)


class RecommendationOut(BaseModel):
    products: list[ProductOut]
    intent: IntentResult
