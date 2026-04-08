from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from scraper.products import ProductData
from scraper.stores import StoreData


class TestGetDelistedSkus:
    @pytest.mark.asyncio
    async def test_returns_delisted_skus(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.return_value = MagicMock(all=lambda: [("10327701",), ("99999999",)])

        with patch("scraper.db.products.SessionLocal", mock_factory):
            from scraper.db import get_delisted_skus

            result = await get_delisted_skus()

        assert result == {"10327701", "99999999"}

    @pytest.mark.asyncio
    async def test_returns_empty_set_when_none_delisted(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.return_value = MagicMock(all=lambda: [])

        with patch("scraper.db.products.SessionLocal", mock_factory):
            from scraper.db import get_delisted_skus

            result = await get_delisted_skus()

        assert result == set()


class TestMarkDelisted:
    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_set(self) -> None:
        from scraper.db import mark_delisted

        result = await mark_delisted(set())
        assert result == 0

    @pytest.mark.asyncio
    async def test_executes_and_commits(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.return_value = MagicMock(rowcount=3)

        with patch("scraper.db.products.SessionLocal", mock_factory):
            from scraper.db import mark_delisted

            result = await mark_delisted({"111", "222", "333"})

        assert result == 3
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestClearDelisted:
    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_set(self) -> None:
        from scraper.db import clear_delisted

        result = await clear_delisted(set())
        assert result == 0

    @pytest.mark.asyncio
    async def test_executes_and_commits(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.return_value = MagicMock(rowcount=2)

        with patch("scraper.db.products.SessionLocal", mock_factory):
            from scraper.db import clear_delisted

            result = await clear_delisted({"111", "222"})

        assert result == 2
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestGetProductStates:
    @pytest.mark.asyncio
    async def test_returns_sku_to_state_mapping(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.return_value = MagicMock(
            all=lambda: [
                ("10327701", datetime(2026, 2, 1, 12, 0, tzinfo=UTC), "abc123"),
                ("99999999", datetime(2026, 1, 15, 8, 30, tzinfo=UTC), None),
            ]
        )

        with patch("scraper.db.products.SessionLocal", mock_factory):
            from scraper.db import get_product_states

            result = await get_product_states()

        assert result["10327701"].updated_date == date(2026, 2, 1)
        assert result["10327701"].content_hash == "abc123"
        assert result["99999999"].updated_date == date(2026, 1, 15)
        assert result["99999999"].content_hash is None

    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_empty_db(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.return_value = MagicMock(all=lambda: [])

        with patch("scraper.db.products.SessionLocal", mock_factory):
            from scraper.db import get_product_states

            result = await get_product_states()

        assert result == {}


@pytest.mark.asyncio
async def test_emit_stock_event_rolls_back_on_failure(mock_db_session) -> None:
    mock_session, mock_factory = mock_db_session
    mock_session.execute.side_effect = SQLAlchemyError("connection lost")

    with patch("scraper.db.events.SessionLocal", mock_factory):
        from scraper.db import emit_stock_event

        with pytest.raises(SQLAlchemyError):
            await emit_stock_event("10327701", available=True)

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_old_stock_events_swallows_error(mock_db_session) -> None:
    mock_session, mock_factory = mock_db_session
    mock_session.execute.side_effect = SQLAlchemyError("connection lost")

    with patch("scraper.db.events.SessionLocal", mock_factory):
        from scraper.db import delete_old_stock_events

        # Should NOT raise
        await delete_old_stock_events(days=90)

    mock_session.commit.assert_not_called()


class TestUpsertProduct:
    @pytest.mark.asyncio
    async def test_commits_and_returns_true_on_upsert(self, mock_db_session) -> None:
        """execute succeeds → commit called, no rollback, returns True."""
        mock_session, mock_factory = mock_db_session
        product = ProductData(sku="12345678", name="Test Wine")

        with patch("scraper.db.products.SessionLocal", mock_factory):
            from scraper.db import upsert_product

            result = await upsert_product(product, content_hash="abc123")

        assert result is True
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rolls_back_and_raises_on_db_error(self, mock_db_session) -> None:
        """When session.execute() raises SQLAlchemyError, upsert should rollback and re-raise."""
        mock_session, mock_factory = mock_db_session
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")
        product = ProductData(sku="12345678", name="Test Wine")

        with patch("scraper.db.products.SessionLocal", mock_factory):
            from scraper.db import upsert_product

            with pytest.raises(SQLAlchemyError):
                await upsert_product(product, content_hash="abc123")

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()


class TestUpsertStores:
    def _make_store(self, saq_store_id: str = "23009") -> StoreData:
        return StoreData(
            saq_store_id=saq_store_id,
            name="Du Parc - Fairmount Ouest",
            city="Montréal",
            temporarily_closed=False,
            store_type="SAQ",
            address="5610, avenue du Parc",
            postcode="H2V 4H9",
            telephone="514-274-0498",
            latitude=45.5234,
            longitude=-73.5987,
        )

    @pytest.mark.asyncio
    async def test_skips_empty_list(self) -> None:
        from scraper.db import upsert_stores

        # Should return None without touching the DB
        result = await upsert_stores([])
        assert result is None

    @pytest.mark.asyncio
    async def test_rolls_back_and_raises_on_db_error(self, mock_db_session) -> None:
        mock_session, mock_factory = mock_db_session
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        with patch("scraper.db.stores.SessionLocal", mock_factory):
            from scraper.db import upsert_stores

            with pytest.raises(SQLAlchemyError):
                await upsert_stores([self._make_store()])

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
