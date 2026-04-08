from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.commands.embed import embed_sync
from scraper.constants import EXIT_FATAL, EXIT_OK


def _make_product(**overrides: object) -> dict:
    """Build a product dict with sensible defaults."""
    defaults = {
        "sku": "12345",
        "category": "Vin rouge",
        "taste_tag": "Fruité et généreux",
        "tasting_profile": {"corps": "corsé", "arome": ["cassis"]},
        "grape_blend": None,
        "grape": "Merlot",
        "producer": "Château Test",
        "region": "Bordeaux",
        "appellation": None,
        "designation": None,
        "classification": None,
        "country": "France",
        "vintage": "2021",
        "description": "A fine wine.",
        "_computed_hash": "abc123",
    }
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
class TestEmbedSync:
    @patch("scraper.commands.embed.settings")
    async def test_returns_fatal_when_api_key_missing(self, mock_settings: MagicMock) -> None:
        mock_settings.OPENAI_API_KEY = ""
        result = await embed_sync()
        assert result == EXIT_FATAL

    @patch("scraper.commands.embed.settings")
    @patch("scraper.commands.embed.get_products_needing_embedding", new_callable=AsyncMock)
    async def test_nothing_to_sync(self, mock_get: AsyncMock, mock_settings: MagicMock) -> None:
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_get.return_value = []
        result = await embed_sync()
        assert result == EXIT_OK

    @patch("scraper.commands.embed.settings")
    @patch("scraper.commands.embed.get_products_needing_embedding", new_callable=AsyncMock)
    @patch("scraper.commands.embed.create_embeddings")
    @patch("scraper.commands.embed.bulk_update_embeddings", new_callable=AsyncMock)
    async def test_embeds_all_products_and_persists_vectors(
        self,
        mock_bulk: AsyncMock,
        mock_embed: MagicMock,
        mock_get: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_get.return_value = [_make_product(sku="111"), _make_product(sku="222")]
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]
        mock_bulk.return_value = 2

        result = await embed_sync()

        assert result == EXIT_OK
        mock_embed.assert_called_once()
        mock_bulk.assert_called_once()

        updates = mock_bulk.call_args[0][0]
        assert len(updates) == 2
        assert updates[0]["sku"] == "111"
        assert updates[1]["sku"] == "222"
        assert len(updates[0]["embedding"]) == 1536

    @patch("scraper.commands.embed.settings")
    @patch("scraper.commands.embed.get_products_needing_embedding", new_callable=AsyncMock)
    @patch("scraper.commands.embed.create_embeddings")
    async def test_api_failure(
        self,
        mock_embed: MagicMock,
        mock_get: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_get.return_value = [_make_product()]
        mock_embed.side_effect = Exception("API error")

        result = await embed_sync()
        assert result == EXIT_FATAL

    @patch("scraper.commands.embed.settings")
    @patch("scraper.commands.embed.get_products_needing_embedding", new_callable=AsyncMock)
    async def test_skips_empty_text_products(
        self, mock_get: AsyncMock, mock_settings: MagicMock
    ) -> None:
        """Products with no embedding-relevant fields are skipped."""
        mock_settings.OPENAI_API_KEY = "sk-test"
        # Product with all None fields → empty embedding text
        empty_product = {
            "sku": "999",
            "category": None,
            "taste_tag": None,
            "tasting_profile": None,
            "grape_blend": None,
            "grape": None,
            "producer": None,
            "region": None,
            "appellation": None,
            "designation": None,
            "classification": None,
            "country": None,
            "vintage": None,
            "description": None,
            "_computed_hash": "abc",
        }
        mock_get.return_value = [empty_product]

        result = await embed_sync()
        assert result == EXIT_OK
