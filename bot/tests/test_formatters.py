from bot.formatters import (
    format_delist_notification,
    format_product_line,
    format_product_list,
    format_stock_notification,
    format_watch_list,
)


class TestFormatProductLine:
    def test_full_product(self):
        product = {
            "name": "Mouton Cadet 2022",
            "price": "16.95",
            "availability": True,
            "sku": "10327701",
        }
        result = format_product_line(product, 1)
        assert "[Mouton Cadet 2022](https://www.saq.com/fr/10327701)" in result
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
        assert "page 1/9" in result

    def test_page_indicator_hidden_for_single_page(self):
        products = [
            {"name": f"Wine {i}", "price": "10.00", "availability": True, "sku": f"S{i}"}
            for i in range(3)
        ]
        data = {"products": products, "total": 3, "page": 1, "per_page": 5, "pages": 1}
        result = format_product_list(data)
        assert "page" not in result

    def test_page_indicator_middle_page(self):
        products = [
            {"name": f"Wine {i}", "price": "10.00", "availability": True, "sku": f"S{i}"}
            for i in range(5)
        ]
        data = {"products": products, "total": 20, "page": 3, "per_page": 5, "pages": 4}
        result = format_product_list(data)
        assert "page 3/4" in result


class TestFormatWatchList:
    def test_empty_list(self):
        result = format_watch_list([])
        assert "not watching" in result.lower()
        assert "/watch" in result

    def test_single_watch_with_product(self):
        watches = [
            {
                "watch": {
                    "id": 1,
                    "user_id": "tg:42",
                    "sku": "10327701",
                    "created_at": "2026-01-01",
                },
                "product": {
                    "name": "Mouton Cadet",
                    "price": "16.95",
                    "availability": True,
                    "sku": "10327701",
                },
            },
        ]
        result = format_watch_list(watches)
        assert "*1 watched wine*" in result
        assert "Mouton Cadet" in result
        assert "16.95$" in result
        assert "\u2705" in result
        assert "since Jan 1" in result

    def test_multiple_watches(self):
        watches = [
            {
                "watch": {"id": 1, "user_id": "tg:42", "sku": "A", "created_at": "2026-01-01"},
                "product": {"name": "Wine A", "price": "10.00", "availability": True, "sku": "A"},
            },
            {
                "watch": {"id": 2, "user_id": "tg:42", "sku": "B", "created_at": "2026-01-01"},
                "product": {"name": "Wine B", "price": "20.00", "availability": False, "sku": "B"},
            },
        ]
        result = format_watch_list(watches)
        assert "*2 watched wines*" in result
        assert "Wine A" in result
        assert "Wine B" in result

    def test_watch_with_delisted_product(self):
        watches = [
            {
                "watch": {
                    "id": 1,
                    "user_id": "tg:42",
                    "sku": "GONE123",
                    "created_at": "2026-01-01",
                },
                "product": None,
            },
        ]
        result = format_watch_list(watches)
        assert "GONE123" in result
        assert "no longer available" in result
        assert "since Jan 1" in result


def _notif(**overrides):
    defaults = {
        "sku": "10327701",
        "product_name": "Mouton Cadet",
        "available": True,
        "saq_store_id": None,
        "store_name": None,
        "online_available": True,
    }
    defaults.update(overrides)
    return defaults


class TestFormatStockNotification:
    def test_single_store_restock(self):
        notifs = [_notif(saq_store_id="23009", store_name="Du Parc")]
        result = format_stock_notification(notifs)
        assert "Back in stock" in result
        assert "[Mouton Cadet](https://www.saq.com/fr/10327701)" in result
        assert "\u2022 Du Parc" in result

    def test_multiple_stores_restock(self):
        notifs = [
            _notif(saq_store_id="23009", store_name="Du Parc"),
            _notif(saq_store_id="23010", store_name="Atwater"),
        ]
        result = format_stock_notification(notifs)
        assert "Back in stock" in result
        assert "\u2022 Du Parc" in result
        assert "\u2022 Atwater" in result

    def test_online_only_restock(self):
        notifs = [_notif()]
        result = format_stock_notification(notifs)
        assert "Back in stock online" in result
        assert "[Mouton Cadet]" in result
        assert "\u2022" not in result

    def test_online_only_destock(self):
        notifs = [_notif(available=False)]
        result = format_stock_notification(notifs)
        assert "Out of stock online" in result

    def test_store_restock_with_online_available(self):
        notifs = [_notif(saq_store_id="23009", store_name="Du Parc", online_available=True)]
        result = format_stock_notification(notifs)
        assert "Also available online" in result

    def test_store_destock_with_online_available(self):
        notifs = [
            _notif(
                saq_store_id="23009",
                store_name="Du Parc",
                available=False,
                online_available=True,
            )
        ]
        result = format_stock_notification(notifs)
        assert "Out of stock" in result
        assert "Still available online" in result

    def test_store_events_online_not_available(self):
        notifs = [_notif(saq_store_id="23009", store_name="Du Parc", online_available=False)]
        result = format_stock_notification(notifs)
        assert "available online" not in result.lower()

    def test_store_events_online_unknown(self):
        notifs = [_notif(saq_store_id="23009", store_name="Du Parc", online_available=None)]
        result = format_stock_notification(notifs)
        assert "available online" not in result.lower()

    def test_mixed_online_and_store(self):
        notifs = [
            _notif(),  # online event
            _notif(saq_store_id="23009", store_name="Du Parc"),
        ]
        result = format_stock_notification(notifs)
        assert "\u2022 Online" in result
        assert "\u2022 Du Parc" in result
        # No addendum — "Online" already in bullet list
        assert "Also available online" not in result

    def test_no_product_name_uses_sku(self):
        notifs = [_notif(product_name=None)]
        result = format_stock_notification(notifs)
        assert "10327701" in result

    def test_store_name_fallback_to_store_id(self):
        notifs = [_notif(saq_store_id="23009", store_name=None)]
        result = format_stock_notification(notifs)
        assert "\u2022 23009" in result


class TestFormatDelistNotification:
    def test_includes_product_name_and_link(self):
        notif = _notif(available=False, delisted=True)
        result = format_delist_notification(notif)
        assert "Mouton Cadet" in result
        assert "removed from SAQ" in result
        assert "https://www.saq.com/fr/10327701" in result

    def test_fallback_to_sku_when_no_name(self):
        notif = _notif(available=False, delisted=True, product_name=None)
        result = format_delist_notification(notif)
        assert "10327701" in result

    def test_watch_removed_message(self):
        notif = _notif(available=False, delisted=True)
        result = format_delist_notification(notif)
        assert "watch has been removed" in result.lower()
