from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic

from backend.services.intent import parse_intent


def _mock_tool_use_response(tool_name: str, tool_input: dict) -> MagicMock:
    """Build a mock Claude response with a single tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
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
    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_extracts_category_and_price(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            "search_wines",
            {
                "categories": ["Vin rouge"],
                "min_price": 20,
                "max_price": 30,
                "country": None,
                "semantic_query": "fruité",
            },
        )

        result = await parse_intent("un rouge fruité autour de 25$")

        assert result.intent_type == "recommendation"
        assert result.categories == ["Vin rouge"]
        assert result.min_price == Decimal("20")
        assert result.max_price == Decimal("30")
        assert result.country is None
        assert result.semantic_query == "fruité"

    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_extracts_country(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            "search_wines",
            {
                "categories": ["Vin blanc"],
                "country": "France",
                "semantic_query": "crisp dry white",
            },
        )

        result = await parse_intent("a crisp dry white from France")

        assert result.categories == ["Vin blanc"]
        assert result.country == "France"
        assert result.semantic_query == "crisp dry white"

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
            "search_wines",
            {
                "categories": [],
                "semantic_query": "something for a BBQ with friends",
            },
        )

        result = await parse_intent("something for a BBQ with friends")

        assert result.intent_type == "recommendation"
        assert result.categories == []
        assert result.min_price is None
        assert result.max_price is None
        assert result.semantic_query == "something for a BBQ with friends"

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
        assert result.intent_type == "recommendation"
        assert result.categories == []

    @patch("backend.services.intent.backend_settings")
    async def test_falls_back_when_no_api_key(self, mock_settings: MagicMock) -> None:
        mock_settings.ANTHROPIC_API_KEY = ""

        result = await parse_intent("un rouge")

        assert result.semantic_query == "un rouge"
        assert result.intent_type == "recommendation"
        assert result.categories == []

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
            "search_wines", {"semantic_query": "bold red"}
        )

        result = await parse_intent("bold red")

        assert result.categories == []
        assert result.min_price is None
        assert result.max_price is None
        assert result.country is None
        assert result.semantic_query == "bold red"

    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_wine_chat_tool_returns_wine_chat_intent(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Claude picks wine_chat tool → intent_type='wine_chat'."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            "wine_chat", {"topic": "Burgundy region overview"}
        )

        result = await parse_intent("tell me about Burgundy")

        assert result.intent_type == "wine_chat"
        assert result.semantic_query == "tell me about Burgundy"

    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_off_topic_tool_returns_off_topic_intent(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Claude picks off_topic tool → intent_type='off_topic'."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response("off_topic", {})

        result = await parse_intent("do you sell beer?")

        assert result.intent_type == "off_topic"

    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_no_tool_call_falls_back_to_wine_chat(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """tool_choice=auto may return text without a tool — falls back to wine_chat."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_text_response()

        result = await parse_intent("bonjour")

        assert result.intent_type == "wine_chat"
        assert result.semantic_query == "bonjour"

    @patch("backend.services.intent.get_anthropic_client")
    @patch("backend.services.intent.backend_settings")
    async def test_conversation_history_included_in_messages(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """When history is provided, it is prepended as a prior exchange."""
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = _mock_tool_use_response(
            "search_wines", {"semantic_query": "something lighter"}
        )

        history = "User: bold red\nAssistant: Here are some bold reds."
        await parse_intent("what about something lighter?", conversation_history=history)

        call_messages = mock_client.messages.create.call_args.kwargs["messages"]
        assert len(call_messages) == 1
        assert "Prior conversation" in call_messages[0]["content"]
        assert "what about something lighter?" in call_messages[0]["content"]
