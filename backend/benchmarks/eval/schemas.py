import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).parent / "data"


class TestQuery(BaseModel):
    id: int
    query: str
    tags: list[str] = []
    split: str = "train"
    expected_categories: list[str] = []
    expected_country: str | None = None
    expected_price_max: float | None = None
    should_return_results: bool = True
    notes: str = ""


class RubricDimension(BaseModel):
    name: str
    description: str
    weight: float = 1.0


class DimensionScore(BaseModel):
    score: float = Field(ge=1, le=5)
    justification: str


class ProductSummary(BaseModel):
    """Lightweight product snapshot for eval output (no embeddings, no timestamps)."""

    sku: str
    name: str | None
    category: str | None
    country: str | None
    price: Decimal | None
    producer: str | None
    grape: str | None
    region: str | None
    taste_tag: str | None
    rating: float | None
    review_count: int | None
    online_availability: bool | None
    reason: str = ""


class ParsedIntentSummary(BaseModel):
    """Intent debug artifact — logged, not scored."""

    categories: list[str] = []
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    country: str | None = None
    available_online: bool = True
    semantic_query: str = ""


class QueryScore(BaseModel):
    query_id: int
    query: str
    scores: dict[str, DimensionScore]
    parsed_intent: ParsedIntentSummary
    products: list[ProductSummary]
    summary: str = ""
    error: str | None = None


class EvalReport(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    judge_model: str
    judge_runs: int = 1
    judge_temperature: float = 0.0
    rubric: list[RubricDimension]
    total_queries: int
    query_scores: list[QueryScore]
    averages: dict[str, float]
    tag_averages: dict[str, float] = {}
    weighted_average: float


def load_queries() -> list[TestQuery]:
    path = DATA_DIR / "queries.json"
    raw = json.loads(path.read_text())
    return [TestQuery(**q) for q in raw]


def load_rubric() -> list[RubricDimension]:
    path = DATA_DIR / "rubric.json"
    raw = json.loads(path.read_text())
    return [RubricDimension(**d) for d in raw["dimensions"]]


def to_serializable(obj: Any) -> Any:
    """Convert Decimal and other non-JSON types for json.dumps."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
