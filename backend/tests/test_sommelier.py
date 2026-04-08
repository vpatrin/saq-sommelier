from unittest.mock import AsyncMock, MagicMock, patch

import anthropic

from backend.services.sommelier import _FALLBACK_MESSAGE, _build_messages, sommelier_chat


class TestBuildMessages:
    def test_returns_single_user_message_without_history(self) -> None:
        msgs = _build_messages("What pairs with lamb?")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "What pairs with lamb?"

    def test_includes_prior_conversation_in_user_message_content(self) -> None:
        history = "User: Tell me about Burgundy\nAssistant: Burgundy is a region..."
        msgs = _build_messages("What about the whites?", conversation_history=history)
        assert len(msgs) == 1
        assert "Previous conversation:" in msgs[0]["content"]
        assert "Tell me about Burgundy" in msgs[0]["content"]
        assert "New question: What about the whites?" in msgs[0]["content"]


class TestSommelierChat:
    @patch("backend.services.sommelier.get_anthropic_client")
    @patch("backend.services.sommelier.backend_settings")
    async def test_returns_text_from_claude_api_response(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_settings.HAIKU_TEMPERATURE = 0.3
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Lamb pairs beautifully with Syrah."
        mock_response = MagicMock()
        mock_response.content = [text_block]
        mock_client.messages.create.return_value = mock_response

        result = await sommelier_chat("What pairs with lamb?")
        assert result == "Lamb pairs beautifully with Syrah."

    @patch("backend.services.sommelier.backend_settings")
    async def test_no_api_key_returns_fallback(self, mock_settings: MagicMock) -> None:
        mock_settings.ANTHROPIC_API_KEY = ""
        result = await sommelier_chat("Tell me about Bordeaux")
        assert result == _FALLBACK_MESSAGE

    @patch("backend.services.sommelier.get_anthropic_client")
    @patch("backend.services.sommelier.backend_settings")
    async def test_api_error_returns_fallback(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="fail", request=MagicMock(), body=None
        )

        result = await sommelier_chat("What is tannin?")
        assert result == _FALLBACK_MESSAGE

    @patch("backend.services.sommelier.get_anthropic_client")
    @patch("backend.services.sommelier.backend_settings")
    async def test_no_text_blocks_returns_fallback(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = []
        mock_client.messages.create.return_value = mock_response

        result = await sommelier_chat("Hello")
        assert result == _FALLBACK_MESSAGE

    @patch("backend.services.sommelier.get_anthropic_client")
    @patch("backend.services.sommelier.backend_settings")
    async def test_passes_conversation_history(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        mock_settings.ANTHROPIC_API_KEY = "sk-test"
        mock_settings.HAIKU_TEMPERATURE = 0.3
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "The whites from Burgundy are Chardonnay-based."
        mock_response = MagicMock()
        mock_response.content = [text_block]
        mock_client.messages.create.return_value = mock_response

        history = "User: Tell me about Burgundy\nAssistant: Burgundy is famous for Pinot Noir."
        result = await sommelier_chat("What about the whites?", conversation_history=history)

        assert "Chardonnay" in result
        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        assert "Previous conversation:" in user_msg
        assert "New question: What about the whites?" in user_msg
