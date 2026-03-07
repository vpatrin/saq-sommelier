from decimal import Decimal

from pydantic import BaseModel


class IntentResult(BaseModel):
    """Structured filters extracted from a natural language wine query."""

    categories: list[str] = []
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    country: str | None = None
    available_only: bool = True
    semantic_query: str = ""
