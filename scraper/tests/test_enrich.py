from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from scraper.adobe import AdobeProduct, PaginationCapError
from scraper.commands.enrich import (
    _parse_grape_blend,
    enrich_wines,
    extract_wine_attrs,
)
from scraper.constants import EXIT_FATAL, EXIT_OK


class TestExtractWineAttrs:
    def test_full_attributes(self) -> None:
        attrs = {
            "pastille_gout": "Aromatique et souple",
            "millesime_produit": "2023",
            "portrait_acidite": "présente",
            "portrait_arome": ["cassis", "prune", "sous-bois"],
            "portrait_bois": "équilibré",
            "portrait_bouche": "généreuse",
            "portrait_corps": "mi-corsé",
            "portrait_sucre": "sec",
            "portrait_potentiel_de_garde": "À boire ou à garder 4 ans",
            "portrait_temp_service_de": "16",
            "portrait_temp_service_a": "18",
            "cepage_text": "{'MALB':'96','SYRA':'4'}",
        }
        result = extract_wine_attrs(attrs)

        assert result["taste_tag"] == "Aromatique et souple"
        assert result["vintage"] == "2023"
        assert result["tasting_profile"] == {
            "acidite": "présente",
            "arome": ["cassis", "prune", "sous-bois"],
            "bois": "équilibré",
            "bouche": "généreuse",
            "corps": "mi-corsé",
            "sucre": "sec",
            "potentiel_garde": "À boire ou à garder 4 ans",
            "temp_service": [16, 18],
        }
        assert result["grape_blend"] == [
            {"code": "MALB", "pct": 96},
            {"code": "SYRA", "pct": 4},
        ]

    def test_empty_strings_become_none(self) -> None:
        attrs = {
            "pastille_gout": "",
            "millesime_produit": "",
            "cepage_text": "",
        }
        result = extract_wine_attrs(attrs)

        assert result["taste_tag"] is None
        assert result["vintage"] is None
        assert result["tasting_profile"] is None
        assert result["grape_blend"] is None

    def test_missing_keys_become_none(self) -> None:
        result = extract_wine_attrs({})

        assert result["taste_tag"] is None
        assert result["vintage"] is None
        assert result["tasting_profile"] is None
        assert result["grape_blend"] is None

    def test_partial_portrait(self) -> None:
        attrs = {
            "portrait_corps": "corsé",
            "portrait_sucre": "sec",
        }
        result = extract_wine_attrs(attrs)

        assert result["tasting_profile"] == {"corps": "corsé", "sucre": "sec"}

    def test_temp_service_partial(self) -> None:
        attrs = {"portrait_temp_service_de": "14", "portrait_temp_service_a": ""}
        result = extract_wine_attrs(attrs)

        assert result["tasting_profile"]["temp_service"] == [14, None]

    def test_temp_service_invalid_ignored(self) -> None:
        attrs = {"portrait_temp_service_de": "not_a_number", "portrait_temp_service_a": "18"}
        result = extract_wine_attrs(attrs)

        # Invalid temp parsing is skipped entirely
        assert "temp_service" not in (result["tasting_profile"] or {})


class TestParseGrapeBlend:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ('{"MALB":"96","SYRA":"4"}', [{"code": "MALB", "pct": 96}, {"code": "SYRA", "pct": 4}]),
            ('{"PINO":"100"}', [{"code": "PINO", "pct": 100}]),
            # Adobe returns single-quoted dicts, not valid JSON
            ("{'MALB':'96','SYRA':'4'}", [{"code": "MALB", "pct": 96}, {"code": "SYRA", "pct": 4}]),
            ('{"MALB":"abc"}', [{"code": "MALB", "pct": 0}]),
        ],
        ids=["valid_blend", "single_grape", "single_quoted_adobe", "non_numeric_pct"],
    )
    def test_parses_blend(self, raw: str, expected: list) -> None:
        assert _parse_grape_blend(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        ["", "not json", "{}"],
        ids=["empty_string", "invalid_json", "empty_dict"],
    )
    def test_returns_none(self, raw: str) -> None:
        assert _parse_grape_blend(raw) is None


def _make_product(
    sku: str,
    attrs: dict[str, str | list[str]] | None = None,
) -> AdobeProduct:
    return AdobeProduct(
        sku=sku,
        name=f"Wine {sku}",
        in_stock=True,
        url=None,
        attributes=attrs or {},
    )


class TestEnrichWines:
    @pytest.mark.asyncio
    async def test_fatal_when_no_products_in_db(self) -> None:
        with patch(
            "scraper.commands.enrich.get_all_skus",
            new_callable=AsyncMock,
            return_value=set(),
        ):
            result = await enrich_wines()
        assert result == EXIT_FATAL

    @pytest.mark.asyncio
    async def test_fatal_on_db_error(self) -> None:
        with patch(
            "scraper.commands.enrich.get_all_skus",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("connection lost"),
        ):
            result = await enrich_wines()
        assert result == EXIT_FATAL

    @pytest.mark.asyncio
    async def test_fatal_on_pagination_cap(self) -> None:
        async def mock_search_raises(client, filters, **kwargs):
            if False:
                yield
            raise PaginationCapError(15000, 10000)

        with (
            patch(
                "scraper.commands.enrich.get_all_skus",
                new_callable=AsyncMock,
                return_value={"111"},
            ),
            patch("scraper.commands.enrich.search_products", side_effect=mock_search_raises),
        ):
            result = await enrich_wines()
        assert result == EXIT_FATAL

    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        products = [
            _make_product(
                "111",
                {"pastille_gout": "Fruité et généreux", "millesime_produit": "2021"},
            ),
            _make_product("222", {"pastille_gout": "Aromatique et souple"}),
            _make_product("999"),  # not in DB
        ]

        async def mock_search(client, filters, **kwargs):
            for p in products:
                yield p

        with (
            patch(
                "scraper.commands.enrich.get_all_skus",
                new_callable=AsyncMock,
                return_value={"111", "222", "333"},
            ),
            patch("scraper.commands.enrich.search_products", side_effect=mock_search),
            patch("scraper.commands.enrich.fetch_facets", new_callable=AsyncMock),
            patch(
                "scraper.commands.enrich.bulk_update_wine_attrs",
                new_callable=AsyncMock,
                return_value=2,
            ) as mock_bulk,
        ):
            result = await enrich_wines()

        assert result == EXIT_OK
        mock_bulk.assert_called_once()
        updates = mock_bulk.call_args[0][0]
        # 111 and 222 updated (in DB), 999 skipped (not in DB)
        assert "111" in updates
        assert "222" in updates
        assert "999" not in updates
        assert updates["111"]["taste_tag"] == "Fruité et généreux"
        assert updates["111"]["vintage"] == "2021"

    @pytest.mark.asyncio
    async def test_skips_products_with_no_attrs(self) -> None:
        """Products with all-None extracted attrs should not be collected."""
        products = [_make_product("111")]  # empty attrs → all None

        async def mock_search(client, filters, **kwargs):
            for p in products:
                yield p

        with (
            patch(
                "scraper.commands.enrich.get_all_skus",
                new_callable=AsyncMock,
                return_value={"111"},
            ),
            patch("scraper.commands.enrich.search_products", side_effect=mock_search),
            patch("scraper.commands.enrich.fetch_facets", new_callable=AsyncMock),
            patch(
                "scraper.commands.enrich.bulk_update_wine_attrs",
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_bulk,
        ):
            result = await enrich_wines()

        assert result == EXIT_OK
        # bulk_update not called — no products to update
        mock_bulk.assert_not_called()

    @pytest.mark.asyncio
    async def test_country_partitioning_on_pagination_cap(self) -> None:
        """PaginationCapError on subcategory → falls back to country partitioning."""
        call_count = 0

        async def mock_search(client, filters, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (direct subcategory) hits pagination cap
                if False:
                    yield
                raise PaginationCapError(15000, 10000)
            # Subsequent calls (per country) return products
            yield _make_product("111", {"pastille_gout": "Fruité"})

        with (
            patch(
                "scraper.commands.enrich.get_all_skus",
                new_callable=AsyncMock,
                return_value={"111"},
            ),
            patch("scraper.commands.enrich.search_products", side_effect=mock_search),
            patch(
                "scraper.commands.enrich.fetch_facets",
                new_callable=AsyncMock,
                return_value=["France", "Italie"],
            ),
            patch(
                "scraper.commands.enrich.bulk_update_wine_attrs",
                new_callable=AsyncMock,
                return_value=1,
            ) as mock_bulk,
        ):
            result = await enrich_wines()

        assert result == EXIT_OK
        mock_bulk.assert_called_once()
