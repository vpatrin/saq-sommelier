from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.db.models import EMBEDDING_MODEL_DIMENSIONS

from backend.repositories.recommendations import find_similar
from backend.schemas.recommendation import IntentResult, RecommendationOut
from backend.services.recommendations import recommend


def _fake_product() -> MagicMock:
    """Minimal mock that passes ProductOut.model_validate."""
    p = MagicMock()
    p.sku = "123456"
    p.name = "Test Wine"
    p.category = "Vin rouge"
    p.country = "France"
    p.size = "750 ml"
    p.price = 25.00
    p.online_availability = True
    p.rating = 4.0
    p.review_count = 10
    p.region = "Bordeaux"
    p.appellation = None
    p.designation = None
    p.classification = None
    p.grape = "Merlot"
    p.grape_blend = None
    p.alcohol = "13.5%"
    p.sugar = None
    p.producer = "Test Producer"
    p.vintage = "2020"
    p.taste_tag = "Fruité et généreux"
    p.created_at = "2026-01-01T00:00:00Z"
    p.updated_at = "2026-01-01T00:00:00Z"
    return p


class TestRecommend:
    @pytest.mark.asyncio
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
    ) -> None:
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_parse.return_value = IntentResult(categories=["Vin rouge"], semantic_query="fruité")
        mock_embed.return_value = [0.1] * EMBEDDING_MODEL_DIMENSIONS
        mock_find.return_value = [_fake_product()]

        db = AsyncMock()
        result = await recommend(db, "un rouge fruité")

        assert isinstance(result, RecommendationOut)
        assert len(result.products) == 1
        assert result.products[0].sku == "123456"
        assert result.intent.categories == ["Vin rouge"]

    @pytest.mark.asyncio
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
    ) -> None:
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_parse.return_value = IntentResult(semantic_query="rare wine")
        mock_embed.return_value = [0.1] * EMBEDDING_MODEL_DIMENSIONS
        mock_find.return_value = []

        db = AsyncMock()
        result = await recommend(db, "rare wine")

        assert result.products == []
        assert result.intent.semantic_query == "rare wine"


def _fake_embedding() -> list[float]:
    return [0.1] * EMBEDDING_MODEL_DIMENSIONS


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
