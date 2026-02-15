from src.parser import ProductData, parse_product


class TestParseProductJsonLD:
    def test_extracts_core_fields(self, product_page_html: str) -> None:
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        assert result.sku == "10327701"
        assert result.category == "Vin rouge"
        assert result.country == "France"
        assert result.price == 22.50
        assert result.currency == "CAD"
        assert result.availability is True

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
        assert result.manufacturer == "Château Example"


class TestParseProductHtmlAttrs:
    def test_extracts_wine_attributes(self, product_page_html: str) -> None:
        result = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")

        assert result.region == "Bordeaux"
        assert result.appellation == "Bordeaux AOC"
        assert result.grape == "Merlot 60 %, Cabernet sauvignon 40 %"
        assert result.alcohol == "13,5 %"
        assert result.sugar == "2,5 g/L"
        assert result.saq_code == "10327701"


class TestParseProductEdgeCases:
    def test_minimal_product(self, minimal_product_html: str) -> None:
        result = parse_product(minimal_product_html, url="https://www.saq.com/fr/99999999")

        assert result.name == "Minimal Wine"
        assert result.sku == "99999999"
        assert result.availability is False
        assert result.price is None
        assert result.region is None
        assert result.grape is None

    def test_no_jsonld_returns_empty_fields(self) -> None:
        html = "<html><body><p>Not a product page</p></body></html>"
        result = parse_product(html, url="https://www.saq.com/fr/test")

        assert result.name is None
        assert result.price is None
        assert isinstance(result, ProductData)


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


class TestProductDataToDict:
    def test_returns_all_fields(self, product_page_html: str) -> None:
        product = parse_product(product_page_html, url="https://www.saq.com/fr/10327701")
        d = product.to_dict()

        assert isinstance(d, dict)
        assert d["sku"] == "10327701"
        assert d["price"] == 22.50
        assert d["region"] == "Bordeaux"
        assert d["url"] == "https://www.saq.com/fr/10327701"

    def test_none_fields_included(self) -> None:
        product = ProductData(name="Test Wine", sku="123")
        d = product.to_dict()

        # None fields are present (not filtered out) — DB needs them for upserts
        assert "price" in d
        assert d["price"] is None
        assert d["name"] == "Test Wine"

    def test_matches_dataclass_fields(self) -> None:
        """Dict keys must match ProductData field names exactly."""
        import dataclasses

        product = ProductData()
        d = product.to_dict()

        field_names = {f.name for f in dataclasses.fields(ProductData)}
        assert set(d.keys()) == field_names
