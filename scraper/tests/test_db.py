from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.parser import ProductData


class TestUpsertProduct:
    @pytest.mark.asyncio
    async def test_commits_on_successful_upsert(self) -> None:
        """Happy path: execute succeeds → commit called, no rollback."""
        mock_session = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        product = ProductData(sku="12345678", name="Test Wine")

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import upsert_product

            await upsert_product(product)

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rolls_back_and_raises_on_db_error(self) -> None:
        """When session.execute() raises SQLAlchemyError, upsert should rollback and re-raise."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        # _SessionLocal() is a sync call that returns an async context manager
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        product = ProductData(sku="12345678", name="Test Wine")

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import upsert_product

            with pytest.raises(SQLAlchemyError):
                await upsert_product(product)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
