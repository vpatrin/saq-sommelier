from bot.keyboards import build_filter_keyboard


class TestBuildFilterKeyboard:
    def _facets(self, categories: list[str] | None = None) -> dict:
        return {
            "categories": ["Rouge", "Blanc", "Rosé"] if categories is None else categories,
            "countries": ["France"],
            "regions": [],
            "grapes": [],
            "price_range": {"min": 10, "max": 100},
        }

    def test_no_active_filters(self):
        kb = build_filter_keyboard(self._facets(), {})
        # Row 0: categories, Row 1: price buckets, no clear row
        assert len(kb.inline_keyboard) == 2
        assert kb.inline_keyboard[0][0].text == "Rouge"
        assert kb.inline_keyboard[0][0].callback_data == "f:cat:Rouge"

    def test_active_category_shows_checkmark(self):
        kb = build_filter_keyboard(self._facets(), {"category": "Rouge"})
        # 3 rows: categories, price, clear
        assert len(kb.inline_keyboard) == 3
        assert kb.inline_keyboard[0][0].text == "\u2713 Rouge"
        assert kb.inline_keyboard[0][1].text == "Blanc"

    def test_active_price_shows_checkmark(self):
        kb = build_filter_keyboard(self._facets(), {"price": "15-25"})
        price_row = kb.inline_keyboard[1]
        assert price_row[0].text == "\u2713 15-25$"
        assert price_row[1].text == "25-50$"

    def test_clear_row_when_filters_active(self):
        kb = build_filter_keyboard(self._facets(), {"category": "Blanc"})
        last_row = kb.inline_keyboard[-1]
        assert len(last_row) == 1
        assert last_row[0].callback_data == "f:clear"

    def test_no_clear_row_when_no_filters(self):
        kb = build_filter_keyboard(self._facets(), {})
        for row in kb.inline_keyboard:
            for btn in row:
                assert btn.callback_data != "f:clear"

    def test_empty_categories(self):
        kb = build_filter_keyboard(self._facets(categories=[]), {})
        # Only price row, no category row
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data.startswith("f:price:")
