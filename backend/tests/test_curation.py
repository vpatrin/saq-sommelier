from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.schemas.recommendation import IntentResult
from backend.services.curation import (
    ExplanationResult,
    _build_user_message,
    _fallback,
    _format_wine,
    _parse_tool_input,
    explain_recommendations,
)


def _fake_product(
    *,
    name: str = "Test Wine",
    grape: str = "Merlot",
    region: str = "Bordeaux",
    country: str = "France",
    price: float = 25.00,
    taste_tag: str = "Fruité",
) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.grape = grape
    p.region = region
    p.country = country
    p.price = price
    p.taste_tag = taste_tag
    return p


class TestFormatWine:
    def test_full_attributes(self) -> None:
        p = _fake_product()
        result = _format_wine(0, p)
        assert "1. Test Wine" in result
        assert "Merlot" in result
        assert "Bordeaux" in result
        assert "France" in result
        assert "25.0$" in result
        assert "Fruité" in result

    def test_missing_attributes(self) -> None:
        p = _fake_product(grape=None, region=None, taste_tag=None)
        p.grape = None
        p.region = None
        p.taste_tag = None
        result = _format_wine(0, p)
        assert "Test Wine" in result
        assert "Grape" not in result
        assert "Region" not in result


class TestBuildUserMessage:
    def test_includes_query_and_wines(self) -> None:
        intent = IntentResult(semantic_query="bold red")
        products = [_fake_product(), _fake_product(name="Second Wine")]
        msg = _build_user_message("bold red wine", intent, products)
        assert "Query: bold red wine" in msg
        assert "Test Wine" in msg
        assert "Second Wine" in msg


class TestParseToolInput:
    def test_valid_input(self) -> None:
        tool_input = {
            "reasons": ["Good match", "Nice diversity"],
            "summary": "Two great picks",
        }
        result = _parse_tool_input(tool_input, 2)
        assert result.reasons == ["Good match", "Nice diversity"]
        assert result.summary == "Two great picks"

    def test_pads_short_reasons(self) -> None:
        tool_input = {"reasons": ["Only one"], "summary": "Summary"}
        result = _parse_tool_input(tool_input, 3)
        assert len(result.reasons) == 3
        assert result.reasons[0] == "Only one"
        assert result.reasons[1] == ""

    def test_truncates_long_reasons(self) -> None:
        tool_input = {"reasons": ["A", "B", "C"], "summary": "Summary"}
        result = _parse_tool_input(tool_input, 2)
        assert len(result.reasons) == 2


class TestFallback:
    def test_returns_empty_reasons(self) -> None:
        result = _fallback(3)
        assert len(result.reasons) == 3
        assert all(r == "" for r in result.reasons)
        assert result.summary == ""


class TestExplainRecommendations:
    @pytest.mark.asyncio
    async def test_empty_products_returns_empty(self) -> None:
        result = await explain_recommendations("query", IntentResult(semantic_query="q"), [])
        assert isinstance(result, ExplanationResult)
        assert result.reasons == []
        assert result.summary == ""

    @pytest.mark.asyncio
    @patch("backend.services.curation.backend_settings")
    async def test_no_api_key_returns_fallback(self, mock_settings: MagicMock) -> None:
        mock_settings.ANTHROPIC_API_KEY = ""
        products = [_fake_product()]
        result = await explain_recommendations("query", IntentResult(semantic_query="q"), products)
        assert len(result.reasons) == 1
        assert result.reasons[0] == ""

    @pytest.mark.asyncio
    @patch("backend.services.curation.get_anthropic_client")
    @patch("backend.services.curation.backend_settings")
    async def test_successful_call(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        # Mock tool_use response
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "explain"
        tool_block.input = {
            "reasons": ["Great Bordeaux red"],
            "summary": "A solid pick",
        }
        mock_response = MagicMock()
        mock_response.content = [tool_block]
        mock_client.messages.create.return_value = mock_response

        products = [_fake_product()]
        result = await explain_recommendations(
            "bold red", IntentResult(semantic_query="bold red"), products
        )
        assert result.reasons == ["Great Bordeaux red"]
        assert result.summary == "A solid pick"

    @pytest.mark.asyncio
    @patch("backend.services.curation.get_anthropic_client")
    @patch("backend.services.curation.backend_settings")
    async def test_api_error_returns_fallback(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        import anthropic

        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="fail", request=MagicMock(), body=None
        )

        products = [_fake_product()]
        result = await explain_recommendations("query", IntentResult(semantic_query="q"), products)
        assert len(result.reasons) == 1
        assert result.reasons[0] == ""

    @pytest.mark.asyncio
    @patch("backend.services.curation.get_anthropic_client")
    @patch("backend.services.curation.backend_settings")
    async def test_no_tool_use_block_returns_fallback(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        text_block = MagicMock()
        text_block.type = "text"
        mock_response = MagicMock()
        mock_response.content = [text_block]
        mock_client.messages.create.return_value = mock_response

        products = [_fake_product()]
        result = await explain_recommendations("query", IntentResult(semantic_query="q"), products)
        assert result.reasons[0] == ""
