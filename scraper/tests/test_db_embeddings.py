from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from scraper.db.embeddings import (
    bulk_update_embeddings,
    bulk_update_wine_attrs,
    get_products_needing_embedding,
)
from scraper.embed import compute_embedding_hash


class TestGetProductsNeedingEmbedding:
    @pytest.mark.asyncio
    async def test_returns_never_embedded_products(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        row = {
            "sku": "10327701",
            "category": "Vin rouge",
            "taste_tag": "Fruité",
            "tasting_profile": None,
            "grape_blend": None,
            "grape": "Merlot",
            "producer": None,
            "region": "Bordeaux",
            "appellation": None,
            "designation": None,
            "classification": None,
            "country": "France",
            "vintage": "2021",
            "description": None,
            "last_embedded_hash": None,
        }
        new_result = MagicMock()
        new_result.all.return_value = [MagicMock(_asdict=lambda: dict(row))]
        existing_result = MagicMock()
        existing_result.all.return_value = []
        mock_session.execute = AsyncMock(side_effect=[new_result, existing_result])

        with patch("scraper.db.embeddings.SessionLocal", mock_factory):
            result = await get_products_needing_embedding()

        assert len(result) == 1
        assert result[0]["sku"] == "10327701"
        assert "_computed_hash" in result[0]

    @pytest.mark.asyncio
    async def test_includes_previously_embedded_products_when_hash_changed(
        self, mock_db_session
    ) -> None:
        mock_session, mock_factory = mock_db_session
        row = {
            "sku": "10327701",
            "category": "Vin rouge",
            "taste_tag": "Fruité",
            "tasting_profile": None,
            "grape_blend": None,
            "grape": "Merlot",
            "producer": None,
            "region": "Bordeaux",
            "appellation": None,
            "designation": None,
            "classification": None,
            "country": "France",
            "vintage": "2021",
            "description": None,
            "last_embedded_hash": "old_hash_that_wont_match",
        }
        new_result = MagicMock()
        new_result.all.return_value = []
        existing_result = MagicMock()
        existing_result.all.return_value = [MagicMock(_asdict=lambda: dict(row))]
        mock_session.execute = AsyncMock(side_effect=[new_result, existing_result])

        with patch("scraper.db.embeddings.SessionLocal", mock_factory):
            result = await get_products_needing_embedding()

        assert len(result) == 1
        assert result[0]["sku"] == "10327701"

    @pytest.mark.asyncio
    async def test_skips_previously_embedded_products_with_matching_hash(
        self, mock_db_session
    ) -> None:
        mock_session, mock_factory = mock_db_session
        attrs = {
            "sku": "10327701",
            "category": "Vin rouge",
            "taste_tag": "Fruité",
            "tasting_profile": None,
            "grape_blend": None,
            "grape": "Merlot",
            "producer": None,
            "region": "Bordeaux",
            "appellation": None,
            "designation": None,
            "classification": None,
            "country": "France",
            "vintage": "2021",
            "description": None,
        }
        current_hash = compute_embedding_hash(attrs)
        row = {**attrs, "last_embedded_hash": current_hash}

        new_result = MagicMock()
        new_result.all.return_value = []
        existing_result = MagicMock()
        existing_result.all.return_value = [MagicMock(_asdict=lambda: dict(row))]
        mock_session.execute = AsyncMock(side_effect=[new_result, existing_result])

        with patch("scraper.db.embeddings.SessionLocal", mock_factory):
            result = await get_products_needing_embedding()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_nothing_needs_embedding(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        new_result = MagicMock()
        new_result.all.return_value = []
        existing_result = MagicMock()
        existing_result.all.return_value = []
        mock_session.execute = AsyncMock(side_effect=[new_result, existing_result])

        with patch("scraper.db.embeddings.SessionLocal", mock_factory):
            result = await get_products_needing_embedding()

        assert result == []


class TestBulkUpdateEmbeddings:
    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_list(self) -> None:
        result = await bulk_update_embeddings([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_commits_and_returns_count(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session

        updates = [
            {"sku": "111", "embedding": [0.1] * 3, "last_embedded_hash": "hash1"},
            {"sku": "222", "embedding": [0.2] * 3, "last_embedded_hash": "hash2"},
        ]

        with patch("scraper.db.embeddings.SessionLocal", mock_factory):
            result = await bulk_update_embeddings(updates)

        assert result == 2
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rolls_back_and_raises_on_db_error(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        updates = [{"sku": "111", "embedding": [0.1] * 3, "last_embedded_hash": "h1"}]

        with (
            patch("scraper.db.embeddings.SessionLocal", mock_factory),
            pytest.raises(SQLAlchemyError),
        ):
            await bulk_update_embeddings(updates)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()


class TestBulkUpdateWineAttrs:
    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_dict(self) -> None:
        result = await bulk_update_wine_attrs({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_commits_and_returns_count(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session

        updates = {
            "111": {
                "taste_tag": "Fruité",
                "vintage": "2021",
                "tasting_profile": None,
                "grape_blend": None,
            },
            "222": {
                "taste_tag": "Corsé",
                "vintage": "2020",
                "tasting_profile": None,
                "grape_blend": None,
            },
        }

        with patch("scraper.db.embeddings.SessionLocal", mock_factory):
            result = await bulk_update_wine_attrs(updates)

        assert result == 2
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rolls_back_and_raises_on_db_error(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        updates = {
            "111": {
                "taste_tag": "Fruité",
                "vintage": None,
                "tasting_profile": None,
                "grape_blend": None,
            },
        }

        with (
            patch("scraper.db.embeddings.SessionLocal", mock_factory),
            pytest.raises(SQLAlchemyError),
        ):
            await bulk_update_wine_attrs(updates)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
