from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.products import ProductData
from src.stores import StoreData


class TestGetDelistedSkus:
    @pytest.mark.asyncio
    async def test_returns_delisted_skus(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(all=lambda: [("10327701",), ("99999999",)])

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import get_delisted_skus

            result = await get_delisted_skus()

        assert result == {"10327701", "99999999"}

    @pytest.mark.asyncio
    async def test_returns_empty_set_when_none_delisted(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(all=lambda: [])

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import get_delisted_skus

            result = await get_delisted_skus()

        assert result == set()


class TestMarkDelisted:
    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_set(self) -> None:
        from src.db import mark_delisted

        result = await mark_delisted(set())
        assert result == 0

    @pytest.mark.asyncio
    async def test_executes_and_commits(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(rowcount=3)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import mark_delisted

            result = await mark_delisted({"111", "222", "333"})

        assert result == 3
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestClearDelisted:
    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_set(self) -> None:
        from src.db import clear_delisted

        result = await clear_delisted(set())
        assert result == 0

    @pytest.mark.asyncio
    async def test_executes_and_commits(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(rowcount=2)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import clear_delisted

            result = await clear_delisted({"111", "222"})

        assert result == 2
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestStoresPopulated:
    @pytest.mark.asyncio
    async def test_returns_true_when_rows_exist(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(first=lambda: ("23009",))

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.db._SessionLocal", MagicMock(return_value=mock_ctx)):
            from src.db import stores_populated

            result = await stores_populated()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_table_empty(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(first=lambda: None)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.db._SessionLocal", MagicMock(return_value=mock_ctx)):
            from src.db import stores_populated

            result = await stores_populated()

        assert result is False


class TestGetUpdatedDates:
    @pytest.mark.asyncio
    async def test_returns_sku_to_date_mapping(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            all=lambda: [
                ("10327701", datetime(2026, 2, 1, 12, 0, tzinfo=UTC)),
                ("99999999", datetime(2026, 1, 15, 8, 30, tzinfo=UTC)),
            ]
        )

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import get_updated_dates

            result = await get_updated_dates()

        assert result == {
            "10327701": date(2026, 2, 1),
            "99999999": date(2026, 1, 15),
        }

    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_empty_db(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(all=lambda: [])

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import get_updated_dates

            result = await get_updated_dates()

        assert result == {}


class TestGetAvailabilityMap:
    @pytest.mark.asyncio
    async def test_returns_sku_to_availability_mapping(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(
            all=lambda: [("10327701", True), ("99999999", False), ("11111111", None)]
        )

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import get_availability_map

            result = await get_availability_map()

        assert result == {"10327701": True, "99999999": False, "11111111": None}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_empty_db(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(all=lambda: [])

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import get_availability_map

            result = await get_availability_map()

        assert result == {}


class TestEmitStockEvent:
    @pytest.mark.asyncio
    async def test_executes_and_commits(self) -> None:
        mock_session = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import emit_stock_event

            await emit_stock_event("10327701", available=True)

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rolls_back_and_raises_on_db_failure(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import emit_stock_event

            with pytest.raises(SQLAlchemyError):
                await emit_stock_event("10327701", available=True)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()


class TestDeleteOldStockEvents:
    @pytest.mark.asyncio
    async def test_executes_and_commits(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.return_value = MagicMock(rowcount=5)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import delete_old_stock_events

            await delete_old_stock_events(days=90)

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_swallows_error_on_db_failure(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import delete_old_stock_events

            # Should NOT raise
            await delete_old_stock_events(days=90)

        mock_session.commit.assert_not_called()


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
        from src.db import upsert_stores

        # Should return None without touching the DB
        result = await upsert_stores([])
        assert result is None

    @pytest.mark.asyncio
    async def test_executes_and_commits(self) -> None:
        mock_session = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        stores = [self._make_store("23009"), self._make_store("23132")]

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import upsert_stores

            await upsert_stores(stores)

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rolls_back_and_raises_on_db_error(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import upsert_stores

            with pytest.raises(SQLAlchemyError):
                await upsert_stores([self._make_store()])

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()


class TestUpsertProductAvailability:
    @pytest.mark.asyncio
    async def test_executes_and_commits(self) -> None:
        mock_session = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import upsert_product_availability

            await upsert_product_availability("10327701", online_available=True)

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rolls_back_and_raises_on_db_error(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_ctx)

        with patch("src.db._SessionLocal", mock_factory):
            from src.db import upsert_product_availability

            with pytest.raises(SQLAlchemyError):
                await upsert_product_availability("10327701", online_available=True)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
