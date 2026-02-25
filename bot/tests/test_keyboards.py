from bot.categories import CATEGORY_FAMILIES
from bot.keyboards import build_filter_keyboard

# Sample grouped data — a few groups have products
_SAMPLE_GROUPED = {
    "rouge": ["Vin rouge"],
    "blanc": ["Vin blanc"],
    "rose": ["Vin rosé"],
    "bulles": ["Champagne", "Vin mousseux"],
    "fortifie": ["Porto blanc"],
    "whisky": ["Whisky écossais"],
    "rhum": ["Rhum agricole"],
    "biere": ["Bière artisanale"],
}


class TestFamilyRow:
    """Family row — always present, 3 buttons."""

    def test_family_row_always_present(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED)
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 3
        assert [btn.callback_data for btn in first_row] == [
            "f:fam:vins",
            "f:fam:spiritueux",
            "f:fam:autres",
        ]

    def test_family_labels(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED)
        labels = [btn.text for btn in kb.inline_keyboard[0]]
        assert labels == ["🍷 Vins", "🥃 Spiritueux", "🍺 Autres"]

    def test_active_family_shows_checkmark(self):
        kb = build_filter_keyboard({"family": "vins"}, _SAMPLE_GROUPED)
        labels = [btn.text for btn in kb.inline_keyboard[0]]
        assert labels == ["✓ 🍷 Vins", "🥃 Spiritueux", "🍺 Autres"]

    def test_family_row_present_even_without_grouped(self):
        kb = build_filter_keyboard({}, None)
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 3


class TestSubgroupRows:
    """Subgroup rows — only when a family is active."""

    def test_no_subgroups_when_no_family(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED)
        # Row 0 = families, Row 1 = prices — no subgroup rows
        assert len(kb.inline_keyboard) == 2

    def test_subgroups_appear_when_family_active(self):
        kb = build_filter_keyboard({"family": "vins"}, _SAMPLE_GROUPED)
        # families + 2 subgroup rows + price + clear
        sub_buttons = [
            btn
            for row in kb.inline_keyboard[1:]
            for btn in row
            if btn.callback_data.startswith("f:cat:")
        ]
        assert len(sub_buttons) == 5  # rouge, blanc, rose, bulles, fortifie
        assert sub_buttons[0].text == "Vin rouge"
        assert sub_buttons[0].callback_data == "f:cat:rouge"

    def test_subgroups_chunked_into_rows_of_3(self):
        kb = build_filter_keyboard({"family": "vins"}, _SAMPLE_GROUPED)
        # 5 subgroups → row of 3 + row of 2
        sub_row_1 = kb.inline_keyboard[1]
        sub_row_2 = kb.inline_keyboard[2]
        assert len(sub_row_1) == 3
        assert len(sub_row_2) == 2

    def test_active_subgroup_shows_checkmark(self):
        kb = build_filter_keyboard({"family": "vins", "category": "rouge"}, _SAMPLE_GROUPED)
        sub_buttons = [
            btn
            for row in kb.inline_keyboard[1:]
            for btn in row
            if btn.callback_data.startswith("f:cat:")
        ]
        assert sub_buttons[0].text == "\u2713 Vin rouge"
        assert sub_buttons[1].text == "Vin blanc"

    def test_empty_subgroups_hidden_with_grouped(self):
        """Spiritueux family: only whisky and rhum are in _SAMPLE_GROUPED."""
        kb = build_filter_keyboard({"family": "spiritueux"}, _SAMPLE_GROUPED)
        sub_buttons = [
            btn
            for row in kb.inline_keyboard[1:]
            for btn in row
            if btn.callback_data.startswith("f:cat:")
        ]
        labels = [btn.text for btn in sub_buttons]
        assert labels == ["Whisky", "Rhum"]

    def test_all_subgroups_shown_when_grouped_is_none(self):
        """Without facets data, show all children of the active family."""
        kb = build_filter_keyboard({"family": "vins"}, None)
        sub_buttons = [
            btn
            for row in kb.inline_keyboard[1:]
            for btn in row
            if btn.callback_data.startswith("f:cat:")
        ]
        vins_children = CATEGORY_FAMILIES["vins"].children
        assert len(sub_buttons) == len(vins_children)

    def test_switching_family_shows_different_subgroups(self):
        kb = build_filter_keyboard({"family": "autres"}, _SAMPLE_GROUPED)
        sub_buttons = [
            btn
            for row in kb.inline_keyboard[1:]
            for btn in row
            if btn.callback_data.startswith("f:cat:")
        ]
        # Only biere is in _SAMPLE_GROUPED for the "autres" family
        assert len(sub_buttons) == 1
        assert sub_buttons[0].text == "Bière"


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
        # No family active → Row 0 = families, Row 1 = prices
        price_row = kb.inline_keyboard[1]
        assert len(price_row) == 4
        assert price_row[0].callback_data == "f:price:15-25"

    def test_active_price_shows_checkmark(self):
        kb = build_filter_keyboard({"price": "25-50"}, _SAMPLE_GROUPED)
        price_row = kb.inline_keyboard[-2]  # second to last (before clear)
        assert price_row[1].text == "\u2713 25-50$"

    def test_clear_row_when_filters_active(self):
        kb = build_filter_keyboard({"family": "vins"}, _SAMPLE_GROUPED)
        last_row = kb.inline_keyboard[-1]
        assert len(last_row) == 1
        assert last_row[0].callback_data == "f:clear"
        assert "Effacer" in last_row[0].text

    def test_no_clear_row_when_no_filters(self):
        kb = build_filter_keyboard({}, _SAMPLE_GROUPED)
        for row in kb.inline_keyboard:
            for btn in row:
                assert btn.callback_data != "f:clear"
