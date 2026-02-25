from bot.keyboards import build_filter_keyboard

# Sample grouped data — a few groups have products
_SAMPLE_GROUPED = {
    "rouge": ["Vin rouge"],
    "blanc": ["Vin blanc"],
    "rose": ["Vin rosé"],
    "bulles": ["Champagne", "Vin mousseux"],
    "whisky": ["Whisky écossais"],
    "rhum": ["Rhum agricole"],
    "biere": ["Bière artisanale"],
}


class TestWineTypeRow:
    """Wine type row — always present, 4 buttons (rouge/blanc/rosé/bulles)."""

    def test_wine_type_row_always_present(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED)
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 4
        assert [btn.callback_data for btn in first_row] == [
            "f:cat:rouge",
            "f:cat:blanc",
            "f:cat:rose",
            "f:cat:bulles",
        ]

    def test_wine_type_labels(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED)
        labels = [btn.text for btn in kb.inline_keyboard[0]]
        assert labels == ["🍷 Rouge", "🥂 Blanc", "🌸 Rosé", "🍾 Bulles"]

    def test_active_category_shows_checkmark(self):
        kb = build_filter_keyboard({"category": "rouge"}, _SAMPLE_GROUPED)
        labels = [btn.text for btn in kb.inline_keyboard[0]]
        assert labels == ["✓ 🍷 Rouge", "🥂 Blanc", "🌸 Rosé", "🍾 Bulles"]

    def test_empty_groups_hidden_with_grouped(self):
        """Only groups present in grouped_categories are shown."""
        sparse = {"rouge": ["Vin rouge"], "bulles": ["Champagne"]}
        kb = build_filter_keyboard({}, sparse)
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 2
        assert [btn.callback_data for btn in first_row] == ["f:cat:rouge", "f:cat:bulles"]

    def test_all_groups_shown_when_grouped_is_none(self):
        """Without facets data, show all 4 wine types."""
        kb = build_filter_keyboard({}, None)
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 4


class TestPaginationRow:
    """Pagination row — only when total_pages > 1."""

    def test_no_pagination_single_page(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED, current_page=1, total_pages=1)
        for row in kb.inline_keyboard:
            for btn in row:
                assert btn.callback_data not in ("f:page:next", "f:page:prev", "noop")

    def test_pagination_shown_on_first_page(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED, current_page=1, total_pages=5)
        page_row = [
            row for row in kb.inline_keyboard if any(btn.callback_data == "noop" for btn in row)
        ]
        assert len(page_row) == 1
        buttons = page_row[0]
        # First page: no prev, page indicator, next
        assert len(buttons) == 2
        assert "1/5" in buttons[0].text
        assert buttons[1].callback_data == "f:page:next"

    def test_pagination_shown_on_middle_page(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED, current_page=3, total_pages=5)
        page_row = [
            row for row in kb.inline_keyboard if any(btn.callback_data == "noop" for btn in row)
        ]
        buttons = page_row[0]
        # Middle page: prev, page indicator, next
        assert len(buttons) == 3
        assert buttons[0].callback_data == "f:page:prev"
        assert "3/5" in buttons[1].text
        assert buttons[2].callback_data == "f:page:next"

    def test_pagination_shown_on_last_page(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED, current_page=5, total_pages=5)
        page_row = [
            row for row in kb.inline_keyboard if any(btn.callback_data == "noop" for btn in row)
        ]
        buttons = page_row[0]
        # Last page: prev, page indicator, no next
        assert len(buttons) == 2
        assert buttons[0].callback_data == "f:page:prev"
        assert "5/5" in buttons[1].text


class TestPriceAndClearRows:
    """Price row + clear row behavior."""

    def test_price_row_always_present(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED)
        # No filters → Row 0 = wine types, Row 1 = prices
        price_row = kb.inline_keyboard[1]
        assert len(price_row) == 4
        assert price_row[0].callback_data == "f:price:15-25"

    def test_active_price_shows_checkmark(self):
        kb = build_filter_keyboard({"price": "25-50"}, _SAMPLE_GROUPED)
        price_row = kb.inline_keyboard[-2]  # second to last (before clear)
        assert price_row[1].text == "\u2713 25-50$"

    def test_clear_row_when_filters_active(self):
        kb = build_filter_keyboard({"category": "rouge"}, _SAMPLE_GROUPED)
        last_row = kb.inline_keyboard[-1]
        assert len(last_row) == 1
        assert last_row[0].callback_data == "f:clear"
        assert "Effacer" in last_row[0].text

    def test_no_clear_row_when_no_filters(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED)
        for row in kb.inline_keyboard:
            for btn in row:
                assert btn.callback_data != "f:clear"
