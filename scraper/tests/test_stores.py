import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from scraper.stores import StoreData, fetch_stores, parse_store


def _raw_store(
    identifier: str = "23009",
    name: str = "Du Parc - Fairmount Ouest",
    city: str = "Montréal",
    temporarily_closed: bool = False,
    store_type_label: str | None = "SAQ",
    address1: str | None = "5610, avenue du Parc",
    postcode: str | None = "H2V 4H9",
    telephone: str | None = "514-274-0498",
    latitude: str | None = "45.5234",
    longitude: str | None = "-73.5987",
) -> dict:
    """Build a minimal raw SAQ API store dict."""
    d: dict = {
        "identifier": identifier,
        "name": name,
        "city": city,
        "temporarily_closed": temporarily_closed,
        "address1": address1,
        "postcode": postcode,
        "telephone": telephone,
        "latitude": latitude,
        "longitude": longitude,
        "additional_attributes": {"type": {"label": store_type_label}} if store_type_label else {},
    }
    return d


def _make_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(data).encode(),
        request=httpx.Request("GET", "https://test"),
    )


def _store_page(stores: list[dict], total: int, is_last_page: bool) -> dict:
    return {"list": stores, "total": total, "is_last_page": is_last_page}


class TestParseStore:
    def test_extracts_all_fields(self) -> None:
        raw = _raw_store()
        result = parse_store(raw)

        assert result.saq_store_id == "23009"
        assert result.name == "Du Parc - Fairmount Ouest"
        assert result.city == "Montréal"
        assert result.temporarily_closed is False
        assert result.store_type == "SAQ"
        assert result.address == "5610, avenue du Parc"
        assert result.postcode == "H2V 4H9"
        assert result.telephone == "514-274-0498"
        assert result.latitude == pytest.approx(45.5234)
        assert result.longitude == pytest.approx(-73.5987)

    def test_converts_lat_lng_from_string(self) -> None:
        raw = _raw_store(latitude="45.1234", longitude="-73.9876")
        result = parse_store(raw)

        assert isinstance(result.latitude, float)
        assert isinstance(result.longitude, float)

    def test_missing_lat_lng_becomes_none(self) -> None:
        raw = _raw_store(latitude=None, longitude=None)
        result = parse_store(raw)

        assert result.latitude is None
        assert result.longitude is None

    def test_missing_store_type_becomes_none(self) -> None:
        raw = _raw_store(store_type_label=None)
        result = parse_store(raw)

        assert result.store_type is None

    def test_temporarily_closed_true(self) -> None:
        raw = _raw_store(temporarily_closed=True)
        result = parse_store(raw)

        assert result.temporarily_closed is True

    def test_missing_optional_fields_become_none(self) -> None:
        raw = _raw_store(address1=None, postcode=None, telephone=None)
        result = parse_store(raw)

        assert result.address is None
        assert result.postcode is None
        assert result.telephone is None


class TestFetchStores:
    @pytest.mark.asyncio
    async def test_returns_all_stores_single_page(self) -> None:
        raw = _raw_store()
        page = _store_page([raw], total=1, is_last_page=True)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _make_response(page)

        with patch("scraper.stores.asyncio.sleep"):
            result = await fetch_stores(client)

        assert len(result) == 1
        assert isinstance(result[0], StoreData)
        assert result[0].saq_store_id == "23009"

    @pytest.mark.asyncio
    async def test_paginates_across_multiple_pages(self) -> None:
        page1 = _store_page([_raw_store("23009")], total=2, is_last_page=False)
        page2 = _store_page([_raw_store("23132")], total=2, is_last_page=True)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = [
            _make_response(page1),
            _make_response(page2),
        ]

        with patch("scraper.stores.asyncio.sleep"):
            result = await fetch_stores(client)

        assert len(result) == 2
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _make_response({}, status_code=503)

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_stores(client)

    @pytest.mark.asyncio
    async def test_sleeps_between_pages(self) -> None:
        page1 = _store_page([_raw_store("23009")], total=2, is_last_page=False)
        page2 = _store_page([_raw_store("23132")], total=2, is_last_page=True)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = [_make_response(page1), _make_response(page2)]

        with patch("scraper.stores.asyncio.sleep") as mock_sleep:
            await fetch_stores(client)

        # Sleep called once between page 1 and page 2 (not after last page)
        mock_sleep.assert_called_once()


class TestStoreDataAlignment:
    def test_storedata_fields_are_subset_of_store_columns(self) -> None:
        import dataclasses

        from core.db.models import Store

        model_columns = set(Store.__table__.columns.keys())
        data_fields = {f.name for f in dataclasses.fields(StoreData)}
        missing = data_fields - model_columns
        assert not missing, f"StoreData fields not in Store model: {missing}"
