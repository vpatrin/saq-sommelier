from bot.formatters import format_product_line, format_product_list


class TestFormatProductLine:
    def test_full_product(self):
        product = {
            "name": "Mouton Cadet 2022",
            "price": "16.95",
            "availability": True,
            "sku": "10327701",
        }
        result = format_product_line(product, 1)
        assert "[Mouton Cadet 2022](https://www.saq.com/en/10327701)" in result
        assert "16.95$" in result
        assert "\u2705" in result

    def test_unavailable_product(self):
        product = {"name": "Opus One", "price": "499.00", "availability": False, "sku": "999"}
        result = format_product_line(product, 2)
        assert "\u274c" in result

    def test_missing_price(self):
        product = {"name": "Mystery Wine", "price": None, "availability": True, "sku": "000"}
        result = format_product_line(product, 1)
        assert "N/A" in result

    def test_missing_name(self):
        product = {"name": None, "price": "10.00", "availability": True, "sku": "111"}
        result = format_product_line(product, 1)
        assert "Unknown" in result


class TestFormatProductList:
    def test_empty_results(self):
        data = {"products": [], "total": 0, "page": 1, "per_page": 5, "pages": 0}
        assert format_product_list(data) == "No results found."

    def test_single_result(self):
        data = {
            "products": [{"name": "Wine", "price": "10.00", "availability": True, "sku": "A"}],
            "total": 1,
            "page": 1,
            "per_page": 5,
            "pages": 1,
        }
        result = format_product_list(data)
        assert "*1 result*" in result
        assert "showing" not in result

    def test_multiple_results_all_shown(self):
        products = [
            {"name": f"Wine {i}", "price": "10.00", "availability": True, "sku": f"S{i}"}
            for i in range(3)
        ]
        data = {"products": products, "total": 3, "page": 1, "per_page": 5, "pages": 1}
        result = format_product_list(data)
        assert "*3 results*" in result
        assert "showing" not in result

    def test_more_results_than_shown(self):
        products = [
            {"name": f"Wine {i}", "price": "10.00", "availability": True, "sku": f"S{i}"}
            for i in range(5)
        ]
        data = {"products": products, "total": 42, "page": 1, "per_page": 5, "pages": 9}
        result = format_product_list(data)
        assert "*42 results*" in result
        assert "showing 5" in result
