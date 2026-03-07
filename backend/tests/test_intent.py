from decimal import Decimal
from unittest.mock import MagicMock, patch

import anthropic
import pytest

import backend.services.intent as intent_module
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


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset the singleton client between tests."""
    intent_module._client = None
    yield
    intent_module._client = None


class TestParseIntent:
    @patch("backend.services.intent.backend_settings")
    @patch("backend.services.intent.anthropic.Anthropic")
    def test_extracts_category_and_price(
        self, mock_anthropic_cls: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {
                "categories": ["Vin rouge"],
                "min_price": 20,
                "max_price": 30,
                "country": None,
                "available_only": True,
                "semantic_query": "fruité",
            }
        )

        result = parse_intent("un rouge fruité autour de 25$")

        assert result.categories == ["Vin rouge"]
        assert result.min_price == Decimal("20")
        assert result.max_price == Decimal("30")
        assert result.country is None
        assert result.available_only is True
        assert result.semantic_query == "fruité"

    @patch("backend.services.intent.backend_settings")
    @patch("backend.services.intent.anthropic.Anthropic")
    def test_extracts_country(
        self, mock_anthropic_cls: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {
                "categories": ["Vin blanc"],
                "country": "France",
                "semantic_query": "crisp dry white",
            }
        )

        result = parse_intent("a crisp dry white from France")

        assert result.categories == ["Vin blanc"]
        assert result.country == "France"
        assert result.semantic_query == "crisp dry white"

    @patch("backend.services.intent.backend_settings")
    @patch("backend.services.intent.anthropic.Anthropic")
    def test_semantic_only_query(
        self, mock_anthropic_cls: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Query with no structured filters — only semantic intent."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {
                "categories": [],
                "semantic_query": "something for a BBQ with friends",
            }
        )

        result = parse_intent("something for a BBQ with friends")

        assert result.categories == []
        assert result.min_price is None
        assert result.max_price is None
        assert result.semantic_query == "something for a BBQ with friends"

    @patch("backend.services.intent.backend_settings")
    @patch("backend.services.intent.anthropic.Anthropic")
    def test_falls_back_on_api_error(
        self, mock_anthropic_cls: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited",
            request=MagicMock(),
            body=None,
        )

        result = parse_intent("un rouge")

        assert result.semantic_query == "un rouge"
        assert result.categories == []

    @patch("backend.services.intent.backend_settings")
    @patch("backend.services.intent.anthropic.Anthropic")
    def test_falls_back_on_no_tool_use_block(
        self, mock_anthropic_cls: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_text_response()

        result = parse_intent("surprise me")

        assert result.semantic_query == "surprise me"

    @patch("backend.services.intent.backend_settings")
    def test_falls_back_when_no_api_key(self, mock_settings: MagicMock) -> None:
        mock_settings.ANTHROPIC_API_KEY = ""

        result = parse_intent("un rouge")

        assert result.semantic_query == "un rouge"
        assert result.categories == []

    @patch("backend.services.intent.backend_settings")
    @patch("backend.services.intent.anthropic.Anthropic")
    def test_handles_missing_optional_fields(
        self, mock_anthropic_cls: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Claude may omit optional fields — parser handles gracefully."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {"semantic_query": "bold red"}
        )

        result = parse_intent("bold red")

        assert result.categories == []
        assert result.min_price is None
        assert result.max_price is None
        assert result.country is None
        assert result.available_only is True
        assert result.semantic_query == "bold red"

    @patch("backend.services.intent.backend_settings")
    @patch("backend.services.intent.anthropic.Anthropic")
    def test_forces_tool_use(self, mock_anthropic_cls: MagicMock, mock_settings: MagicMock) -> None:
        """Verify we pass tool_choice to force the search_wines tool."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            {"semantic_query": "test"}
        )

        parse_intent("test query")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["tool_choice"] == {"type": "tool", "name": "search_wines"}
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
