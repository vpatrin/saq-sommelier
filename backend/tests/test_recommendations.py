from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.embedding_client import EMBEDDING_DIMENSIONS

from backend.repositories.recommendations import (
    _redundancy_penalty,
    _rerank,
    find_similar,
)
from backend.schemas.recommendation import IntentResult, RecommendationOut
from backend.services.curation import ExplanationResult
from backend.services.recommendations import recommend


def _fake_product(
    *,
    sku: str = "123456",
    producer: str = "Test Producer",
    country: str = "France",
    grape: str = "Merlot",
    region: str = "Bordeaux",
    taste_tag: str = "Fruité et généreux",
    category: str = "Vin rouge",
) -> MagicMock:
    """Minimal mock that passes ProductOut.model_validate."""
    p = MagicMock()
    p.sku = sku
    p.name = "Test Wine"
    p.category = category
    p.country = country
    p.size = "750 ml"
    p.price = 25.00
    p.online_availability = True
    p.rating = 4.0
    p.review_count = 10
    p.region = region
    p.appellation = None
    p.designation = None
    p.classification = None
    p.grape = grape
    p.grape_blend = None
    p.alcohol = "13.5%"
    p.sugar = None
    p.producer = producer
    p.vintage = "2020"
    p.taste_tag = taste_tag
    p.created_at = "2026-01-01T00:00:00Z"
    p.updated_at = "2026-01-01T00:00:00Z"
    return p


class TestRecommend:
    @pytest.mark.asyncio
    @patch("backend.services.recommendations._write_log", new_callable=AsyncMock)
    @patch("backend.services.recommendations.explain_recommendations")
    @patch("backend.services.recommendations.find_similar")
    @patch("backend.services.recommendations.embed_query")
    @patch("backend.services.recommendations.parse_intent")
    @patch("backend.services.recommendations.backend_settings")
    async def test_full_pipeline(
        self,
        mock_settings: MagicMock,
        mock_parse: MagicMock,
        mock_embed: MagicMock,
        mock_find: AsyncMock,
        mock_explain: MagicMock,
        mock_write_log: AsyncMock,
    ) -> None:
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_parse.return_value = IntentResult(categories=["Vin rouge"], semantic_query="fruité")
        mock_embed.return_value = [0.1] * EMBEDDING_DIMENSIONS
        mock_find.return_value = [_fake_product()]
        mock_explain.return_value = ExplanationResult(
            reasons=["Great fruity red"], summary="A fruity selection"
        )
        mock_write_log.return_value = 42

        db = AsyncMock()
        result = await recommend(db, "un rouge fruité", user_id="tg:123")

        assert isinstance(result, RecommendationOut)
        assert len(result.products) == 1
        assert result.products[0].product.sku == "123456"
        assert result.products[0].reason == "Great fruity red"
        assert result.summary == "A fruity selection"
        assert result.intent.categories == ["Vin rouge"]
        assert result.log_id == 42
        mock_write_log.assert_called_once()
        log_kwargs = mock_write_log.call_args.kwargs
        assert log_kwargs["user_id"] == "tg:123"
        assert log_kwargs["query"] == "un rouge fruité"
        assert log_kwargs["returned_skus"] == ["123456"]
        assert "intent" in log_kwargs["latency_ms"]
        assert "total" in log_kwargs["latency_ms"]

    @pytest.mark.asyncio
    @patch("backend.services.recommendations._write_log", new_callable=AsyncMock)
    @patch("backend.services.recommendations.explain_recommendations")
    @patch("backend.services.recommendations.find_similar")
    @patch("backend.services.recommendations.embed_query")
    @patch("backend.services.recommendations.parse_intent")
    @patch("backend.services.recommendations.backend_settings")
    async def test_empty_results(
        self,
        mock_settings: MagicMock,
        mock_parse: MagicMock,
        mock_embed: MagicMock,
        mock_find: AsyncMock,
        mock_explain: MagicMock,
        mock_write_log: AsyncMock,
    ) -> None:
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_parse.return_value = IntentResult(semantic_query="rare wine")
        mock_embed.return_value = [0.1] * EMBEDDING_DIMENSIONS
        mock_find.return_value = []
        mock_explain.return_value = ExplanationResult(reasons=[], summary="")
        mock_write_log.return_value = 1

        db = AsyncMock()
        result = await recommend(db, "rare wine")

        assert result.products == []
        assert result.summary == ""
        assert result.intent.semantic_query == "rare wine"

    @pytest.mark.asyncio
    @patch("backend.services.recommendations._write_log", new_callable=AsyncMock)
    @patch("backend.services.recommendations.parse_intent")
    async def test_non_wine_returns_early_without_logging(
        self,
        mock_parse: MagicMock,
        mock_write_log: AsyncMock,
    ) -> None:
        mock_parse.return_value = IntentResult(is_wine=False, semantic_query="beer")

        db = AsyncMock()
        result = await recommend(db, "give me a beer")

        assert result.products == []
        assert result.log_id is None
        mock_write_log.assert_not_called()

    @pytest.mark.asyncio
    @patch("backend.services.recommendations.parse_intent")
    async def test_pipeline_failure_does_not_log(
        self,
        mock_parse: MagicMock,
    ) -> None:
        mock_parse.side_effect = RuntimeError("API down")

        db = AsyncMock()
        with pytest.raises(RuntimeError, match="API down"):
            await recommend(db, "red wine")


def _fake_embedding() -> list[float]:
    return [0.1] * EMBEDDING_DIMENSIONS


class TestFindSimilar:
    @pytest.mark.asyncio
    async def test_returns_product_list(self) -> None:
        mock_product = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_product]

        db = AsyncMock()
        db.execute.return_value = mock_result

        intent = IntentResult(semantic_query="bold red")
        products = await find_similar(db, intent, _fake_embedding())

        assert products == [mock_product]

    @pytest.mark.asyncio
    async def test_returns_empty_list(self) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = mock_result

        intent = IntentResult(semantic_query="something rare")
        products = await find_similar(db, intent, _fake_embedding())

        assert products == []


class TestRerank:
    def test_passthrough_when_fewer_than_limit(self) -> None:
        candidates = [_fake_product(sku="1"), _fake_product(sku="2")]
        result = _rerank(candidates, limit=5)
        assert result == candidates

    def test_first_pick_is_top_candidate(self) -> None:
        candidates = [
            _fake_product(sku="1", producer="A", grape="Merlot", country="France"),
            _fake_product(sku="2", producer="B", grape="Syrah", country="Italie"),
            _fake_product(sku="3", producer="C", grape="Gamay", country="Espagne"),
        ]
        result = _rerank(candidates, limit=2)
        assert result[0].sku == "1"

    def test_diversifies_by_producer(self) -> None:
        """Same producer for all candidates — reranker should still pick the top,
        then prefer candidates with different attributes."""
        candidates = [
            _fake_product(
                sku="1", producer="Same", grape="Merlot", country="France", region="Bordeaux"
            ),
            _fake_product(
                sku="2", producer="Same", grape="Merlot", country="France", region="Bordeaux"
            ),
            _fake_product(
                sku="3", producer="Different", grape="Syrah", country="Italie", region="Toscana"
            ),
        ]
        result = _rerank(candidates, limit=2)
        # First is always top-ranked; second should prefer the diverse option
        assert result[0].sku == "1"
        assert result[1].sku == "3"

    def test_respects_limit(self) -> None:
        candidates = [_fake_product(sku=str(i)) for i in range(10)]
        result = _rerank(candidates, limit=3)
        assert len(result) == 3


class TestRedundancyPenalty:
    def test_empty_selected_returns_zero(self) -> None:
        candidate = _fake_product()
        assert _redundancy_penalty(candidate, []) == 0.0

    def test_identical_wine_returns_boosted_penalty(self) -> None:
        wine = _fake_product()
        penalty = _redundancy_penalty(wine, [wine])
        # 1.0 base * (1.0 + 0.2 * 1 similar) = 1.2
        assert penalty == pytest.approx(1.2)

    def test_different_attributes_returns_zero_penalty(self) -> None:
        candidate = _fake_product(
            producer="A",
            grape="Syrah",
            country="Italie",
            region="Toscana",
            taste_tag="Corsé",
            category="Vin blanc",
        )
        selected = _fake_product(
            producer="B",
            grape="Merlot",
            country="France",
            region="Bordeaux",
            taste_tag="Fruité",
            category="Vin rouge",
        )
        penalty = _redundancy_penalty(candidate, [selected])
        assert penalty == 0.0

    def test_partial_overlap(self) -> None:
        candidate = _fake_product(producer="A", grape="Merlot", country="France")
        selected = _fake_product(producer="B", grape="Merlot", country="Italie")
        penalty = _redundancy_penalty(candidate, [selected])
        # Same grape (1.0) out of total checks (4.5)
        assert 0.0 < penalty < 1.0

    def test_null_attributes_excluded_from_checks(self) -> None:
        candidate = _fake_product(producer=None, grape=None, country="France")
        selected = _fake_product(producer=None, grape=None, country="France")
        penalty = _redundancy_penalty(candidate, [selected])
        # Only country + taste_tag + region can match
        assert penalty > 0.0
