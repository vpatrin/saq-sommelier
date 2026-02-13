"""Tests for the SAQ product page parser."""

from src.parser import ProductData, parse_product


class TestParseProductJsonLD:
    def test_extracts_core_fields(self, product_page_html: str) -> None:
        result = parse_product(product_page_html)

        assert result.sku == "10327701"
        assert result.category == "Vin rouge"
        assert result.country == "France"
        assert result.price == 22.50
        assert result.currency == "CAD"
        assert result.availability is True

    def test_extracts_rating(self, product_page_html: str) -> None:
        result = parse_product(product_page_html)

        assert result.rating == 4.5
        assert result.review_count == 100

    def test_strips_image_query_params(self, product_page_html: str) -> None:
        result = parse_product(product_page_html)

        assert result.image == "https://www.saq.com/media/image.png"

    def test_unescapes_html_entities(self, product_page_html: str) -> None:
        result = parse_product(product_page_html)

        # &acirc; → â
        assert result.name == "Château Example Bordeaux"
        assert result.manufacturer == "Château Example"


class TestParseProductHtmlAttrs:
    def test_extracts_wine_attributes(self, product_page_html: str) -> None:
        result = parse_product(product_page_html)

        assert result.region == "Bordeaux"
        assert result.appellation == "Bordeaux AOC"
        assert result.grape == "Merlot 60 %, Cabernet sauvignon 40 %"
        assert result.alcohol == "13,5 %"
        assert result.sugar == "2,5 g/L"
        assert result.saq_code == "10327701"


class TestParseProductEdgeCases:
    def test_minimal_product(self, minimal_product_html: str) -> None:
        result = parse_product(minimal_product_html)

        assert result.name == "Minimal Wine"
        assert result.sku == "99999999"
        assert result.availability is False
        assert result.price is None
        assert result.region is None
        assert result.grape is None

    def test_no_jsonld_returns_empty_fields(self) -> None:
        html = "<html><body><p>Not a product page</p></body></html>"
        result = parse_product(html)

        assert result.name is None
        assert result.price is None
        assert isinstance(result, ProductData)
