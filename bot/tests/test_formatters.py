from bot.formatters import (
    format_delist_notification,
    format_product_line,
    format_recommendations,
    format_stock_notification,
    format_watch_list,
)


class TestFormatProductLine:
    def test_full_product(self):
        product = {
            "name": "Mouton Cadet 2022",
            "price": "16.95",
            "online_availability": True,
            "sku": "10327701",
        }
        result = format_product_line(product, 1)
        assert "[Mouton Cadet 2022](https://www.saq.com/fr/10327701)" in result
        assert "16.95$" in result
        assert "\u2705" in result

    def test_unavailable_product(self):
        product = {
            "name": "Opus One",
            "price": "499.00",
            "online_availability": False,
            "sku": "999",
        }
        result = format_product_line(product, 2)
        assert "\u274c" in result

    def test_missing_price(self):
        product = {"name": "Mystery Wine", "price": None, "online_availability": True, "sku": "000"}
        result = format_product_line(product, 1)
        assert "N/A" in result

    def test_missing_name(self):
        product = {"name": None, "price": "10.00", "online_availability": True, "sku": "111"}
        result = format_product_line(product, 1)
        assert "Unknown" in result


class TestFormatRecommendations:
    def test_empty_results(self):
        data = {"products": [], "intent": {"semantic_query": "rare"}}
        result = format_recommendations(data)
        assert "no recommendations" in result.lower()

    def test_single_product_with_details(self):
        data = {
            "products": [
                {
                    "name": "Château Margaux",
                    "price": "89.00",
                    "online_availability": True,
                    "sku": "12345",
                    "grape": "Merlot",
                    "region": "Bordeaux",
                    "country": "France",
                    "taste_tag": "Aromatique et souple",
                    "vintage": "2021",
                }
            ],
            "intent": {"semantic_query": "bold red"},
        }
        result = format_recommendations(data)
        assert "[Château Margaux](https://www.saq.com/fr/12345)" in result
        assert "89.00$" in result
        assert "\u2705" in result
        assert "Merlot" in result
        assert "Bordeaux, France" in result
        assert "Aromatique et souple" in result
        assert "2021" in result

    def test_country_fallback_when_no_region(self):
        data = {
            "products": [
                {
                    "name": "Some Wine",
                    "price": "20.00",
                    "online_availability": True,
                    "sku": "999",
                    "grape": None,
                    "region": None,
                    "country": "Italy",
                }
            ],
            "intent": {"semantic_query": "italian"},
        }
        result = format_recommendations(data)
        assert "Italy" in result

    def test_no_details_line_when_all_none(self):
        data = {
            "products": [
                {
                    "name": "Mystery",
                    "price": "10.00",
                    "online_availability": True,
                    "sku": "000",
                    "grape": None,
                    "region": None,
                    "country": None,
                    "taste_tag": None,
                    "vintage": None,
                }
            ],
            "intent": {"semantic_query": "anything"},
        }
        result = format_recommendations(data)
        assert "Mystery" in result
        lines = result.strip().split("\n")
        # Only the product line, no detail lines
        assert len(lines) == 1

    def test_flat_grape_used_over_grape_blend(self):
        data = {
            "products": [
                {
                    "name": "Blend Wine",
                    "price": "30.00",
                    "online_availability": True,
                    "sku": "555",
                    "grape": "Malbec",
                    "grape_blend": [{"code": "MALB", "pct": 80}, {"code": "MERL", "pct": 20}],
                    "region": "Mendoza",
                    "country": "Argentine",
                }
            ],
            "intent": {"semantic_query": "blend"},
        }
        result = format_recommendations(data)
        assert "Malbec" in result
        assert "MALB" not in result

    def test_region_dedup_when_same_as_country(self):
        data = {
            "products": [
                {
                    "name": "Cretan Wine",
                    "price": "19.00",
                    "online_availability": True,
                    "sku": "777",
                    "grape": "Assyrtiko",
                    "region": "Grèce",
                    "country": "Grèce",
                }
            ],
            "intent": {"semantic_query": "greek"},
        }
        result = format_recommendations(data)
        assert "Grèce, Grèce" not in result
        assert "Grèce" in result

    def test_region_internal_dedup(self):
        """SAQ stores 'Bourgogne, Bourgogne' when sub-region = parent."""
        data = {
            "products": [
                {
                    "name": "Aligoté",
                    "price": "19.00",
                    "online_availability": True,
                    "sku": "888",
                    "grape": "Aligoté",
                    "region": "Bourgogne, Bourgogne",
                    "country": "France",
                }
            ],
            "intent": {"semantic_query": "white burgundy"},
        }
        result = format_recommendations(data)
        assert "Bourgogne, Bourgogne" not in result
        assert "Bourgogne, France" in result


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
                    "online_availability": True,
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
                "product": {
                    "name": "Wine A",
                    "price": "10.00",
                    "online_availability": True,
                    "sku": "A",
                },
            },
            {
                "watch": {"id": 2, "user_id": "tg:42", "sku": "B", "created_at": "2026-01-01"},
                "product": {
                    "name": "Wine B",
                    "price": "20.00",
                    "online_availability": False,
                    "sku": "B",
                },
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
