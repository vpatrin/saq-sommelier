from unittest.mock import MagicMock, patch

from core.embedding_client import _BATCH_SIZE, create_embeddings, embed_query


def _mock_response(count: int, offset: int = 0) -> MagicMock:
    """Build a mock OpenAI embeddings response."""
    resp = MagicMock()
    resp.data = [MagicMock(index=i, embedding=[0.1 * (i + offset)] * 3) for i in range(count)]
    return resp


class TestCreateEmbeddings:
    @patch("core.embedding_client.OpenAI")
    def test_single_batch(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _mock_response(2)

        texts = ["wine A", "wine B"]
        vectors = create_embeddings(texts, api_key="sk-test")

        assert len(vectors) == 2
        mock_client.embeddings.create.assert_called_once()
        call_kwargs = mock_client.embeddings.create.call_args
        assert call_kwargs.kwargs["input"] == texts

    @patch("core.embedding_client.OpenAI")
    def test_multiple_batches(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Create enough texts to trigger 2 batches
        texts = [f"wine {i}" for i in range(_BATCH_SIZE + 5)]
        mock_client.embeddings.create.side_effect = [
            _mock_response(_BATCH_SIZE),
            _mock_response(5),
        ]

        vectors = create_embeddings(texts, api_key="sk-test")

        assert len(vectors) == _BATCH_SIZE + 5
        assert mock_client.embeddings.create.call_count == 2

    @patch("core.embedding_client.OpenAI")
    def test_empty_input(self, mock_openai_cls: MagicMock) -> None:
        vectors = create_embeddings([], api_key="sk-test")
        assert vectors == []


class TestEmbedQuery:
    @patch("core.embedding_client.OpenAI")
    def test_returns_single_vector(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = _mock_response(1)

        vector = embed_query("bold red wine", api_key="sk-test")

        assert isinstance(vector, list)
        assert len(vector) == 3
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small", input=["bold red wine"]
        )
