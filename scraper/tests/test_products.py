from scraper.products import ProductData, compute_content_hash, parse_product


class TestParseProductJsonLD:
    def test_extracts_core_fields(self, product_page_html: str) -> None:
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        assert result.sku == "10327701"
        assert result.category == "Vin rouge"
        assert result.price == 22.50
        assert result.online_availability is True

    def test_extracts_rating(self, product_page_html: str) -> None:
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        assert result.rating == 4.5
        assert result.review_count == 100

    def test_strips_image_query_params(self, product_page_html: str) -> None:
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        assert result.image == "https://www.saq.com/media/image.png"

    def test_unescapes_html_entities(self, product_page_html: str) -> None:
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        # &acirc; → â
        assert result.name == "Château Example Bordeaux"

    def test_merges_multiple_jsonld_blocks(self, product_page_html: str) -> None:
        """Rating from block 2 is merged with price from block 1."""
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        # Block 1 has price, block 2 has rating — both should be present
        assert result.price == 22.50
        assert result.rating == 4.5
        assert result.review_count == 100

    def test_accepts_bytes_input(self, product_page_html_bytes: bytes) -> None:
        """Parser handles raw bytes (response.content) for correct encoding."""
        result = parse_product(product_page_html_bytes, url="https://www.saq.com/fr/10327701")

        assert result.sku == "10327701"
        assert result.name == "Château Example Bordeaux"
        assert result.price == 22.50

    def test_bytes_input_preserves_accented_characters(self) -> None:
        """UTF-8 bytes with accents are decoded correctly (prevents mojibake)."""
        html = """<html><head>
<script type="application/ld+json">
{"@type": "Product", "name": "Bière dorée", "sku": "11111111",
 "category": "Bière dorée de type Lager"}
</script>
</head><body></body></html>""".encode()
        result = parse_product(html, url="https://www.saq.com/fr/11111111")

        assert result.name == "Bière dorée"
        assert result.category == "Bière dorée de type Lager"

    def test_parses_price_with_thousands_separator(self) -> None:
        """Price "1,624.75" (thousands comma) is parsed correctly."""
        html = """<html><head>
<script type="application/ld+json">
{"@type": "Product", "name": "Expensive Wine", "offers": {"price": "1,624.75"}}
</script>
</head><body></body></html>"""
        result = parse_product(html, url="https://www.saq.com/fr/15411110")

        assert result.price == 1624.75

    def test_french_decimal_comma_in_rating(self, product_page_html: str) -> None:
        """Rating value "4,5" (French comma) is parsed correctly."""
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        assert result.rating == 4.5


class TestParseProductHtmlAttrs:
    def test_extracts_wine_attributes(self, product_page_html: str) -> None:
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        assert result.country == "France"
        assert result.size == "750 ml"
        assert result.region == "Bordeaux"
        assert result.appellation == "Bordeaux AOC"
        assert result.grape == "Merlot 60 %, Cabernet sauvignon 40 %"
        assert result.alcohol == "13,5 %"
        assert result.sugar == "2,5 g/L"


class TestParseProductEdgeCases:
    def test_minimal_product(self, minimal_product_html: str) -> None:
        result = parse_product(minimal_product_html, url="https://www.saq.com/fr/99999999")

        assert result.name == "Minimal Wine"
        assert result.sku == "99999999"
        assert result.online_availability is False
        assert result.price is None
        assert result.region is None
        assert result.grape is None

    def test_malformed_jsonld_returns_empty_fields(self) -> None:
        html = """<html><head>
<script type="application/ld+json">{not valid json at all}</script>
</head><body></body></html>"""
        result = parse_product(html, url="https://www.saq.com/fr/broken")

        assert result.sku is None
        assert result.name is None
        assert result.price is None
        assert isinstance(result, ProductData)

    def test_no_jsonld_returns_empty_fields(self) -> None:
        html = "<html><body><p>Not a product page</p></body></html>"
        result = parse_product(html, url="https://www.saq.com/fr/test")

        assert result.name is None
        assert result.price is None
        assert isinstance(result, ProductData)


class TestComputeContentHash:
    def test_same_product_same_hash(self) -> None:
        p = ProductData(sku="123", name="Wine", price=20.0)
        assert compute_content_hash(p) == compute_content_hash(p)

    def test_different_products_different_hash(self) -> None:
        p1 = ProductData(sku="123", name="Wine A", price=20.0)
        p2 = ProductData(sku="123", name="Wine B", price=20.0)
        assert compute_content_hash(p1) != compute_content_hash(p2)

    def test_none_fields_excluded(self) -> None:
        """Hash should be stable regardless of which fields are None."""
        p1 = ProductData(sku="123", name="Wine")
        p2 = ProductData(sku="123", name="Wine", price=None)
        assert compute_content_hash(p1) == compute_content_hash(p2)

    def test_returns_hex_string(self) -> None:
        p = ProductData(sku="123")
        h = compute_content_hash(p)
        assert len(h) == 64  # SHA256 hex digest
        assert all(c in "0123456789abcdef" for c in h)


class TestProductDataAlignment:
    def test_product_data_fields_exist_on_model(self) -> None:
        """Every ProductData field must map to a Product column.

        Catches renames in the ORM model that would silently break upserts
        (unknown columns ignored or raising at DB level).
        """
        import dataclasses

        from core.db.models import Product

        model_columns = set(Product.__table__.columns.keys())
        data_fields = {f.name for f in dataclasses.fields(ProductData)}
        missing = data_fields - model_columns
        assert not missing, f"ProductData fields not in Product model: {missing}"
