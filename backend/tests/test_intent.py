from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from backend.services.intent import parse_intent


def _mock_tool_use_response(tool_input: dict) -> MagicMock:
    """Build a mock Claude response with a single tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "search_wines"
    block.input = tool_input

    response = MagicMock()
    response.content = [block]
    return response


def _mock_text_response() -> MagicMock:
    """Build a mock Claude response with only a text block (no tool_use)."""
    block = MagicMock()
    block.type = "text"

    response = MagicMock()
    response.content = [block]
    return response


class TestParseIntent:
    @pytest.mark.asyncio
    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_extracts_category_and_price(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {
                "categories": ["Vin rouge"],
                "min_price": 20,
                "max_price": 30,
                "country": None,
                "semantic_query": "fruité",
            }
        )

        result = await parse_intent("un rouge fruité autour de 25$")

        assert result.categories == ["Vin rouge"]
        assert result.min_price == Decimal("20")
        assert result.max_price == Decimal("30")
        assert result.country is None
        assert result.semantic_query == "fruité"

    @pytest.mark.asyncio
    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_extracts_country(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {
                "categories": ["Vin blanc"],
                "country": "France",
                "semantic_query": "crisp dry white",
            }
        )

        result = await parse_intent("a crisp dry white from France")

        assert result.categories == ["Vin blanc"]
        assert result.country == "France"
        assert result.semantic_query == "crisp dry white"

    @pytest.mark.asyncio
    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_semantic_only_query(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Query with no structured filters — only semantic intent."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {
                "categories": [],
                "semantic_query": "something for a BBQ with friends",
            }
        )

        result = await parse_intent("something for a BBQ with friends")

        assert result.categories == []
        assert result.min_price is None
        assert result.max_price is None
        assert result.semantic_query == "something for a BBQ with friends"

    @pytest.mark.asyncio
    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_falls_back_on_api_error(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited",
            request=MagicMock(),
            body=None,
        )

        result = await parse_intent("un rouge")

        assert result.semantic_query == "un rouge"
        assert result.categories == []

    @pytest.mark.asyncio
    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_falls_back_on_no_tool_use_block(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_text_response()

        result = await parse_intent("surprise me")

        assert result.semantic_query == "surprise me"

    @pytest.mark.asyncio
    @patch("backend.services.intent.backend_settings")
    async def test_falls_back_when_no_api_key(self, mock_settings: MagicMock) -> None:
        mock_settings.ANTHROPIC_API_KEY = ""

        result = await parse_intent("un rouge")

        assert result.semantic_query == "un rouge"
        assert result.categories == []

    @pytest.mark.asyncio
    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_handles_missing_optional_fields(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Claude may omit optional fields — parser handles gracefully."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {"semantic_query": "bold red"}
        )

        result = await parse_intent("bold red")

        assert result.categories == []
        assert result.min_price is None
        assert result.max_price is None
        assert result.country is None
        assert result.semantic_query == "bold red"
