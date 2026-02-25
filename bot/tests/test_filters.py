from unittest.mock import AsyncMock

import pytest

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.handlers.filters import (
    build_api_params,
    filter_callback,
    toggle_category,
    toggle_family,
    toggle_price,
)

# ── Toggle helpers ─────────────────────────────────────────────


class TestToggleCategory:
    def test_select(self):
        filters = {}
        toggle_category(filters, "rouge")
        assert filters["category"] == "rouge"

    def test_deselect(self):
        filters = {"category": "rouge"}
        toggle_category(filters, "rouge")
        assert "category" not in filters

    def test_switch(self):
        filters = {"category": "rouge"}
        toggle_category(filters, "blanc")
        assert filters["category"] == "blanc"


class TestToggleFamily:
    def test_select(self):
        filters = {}
        toggle_family(filters, "vins")
        assert filters["family"] == "vins"

    def test_deselect(self):
        filters = {"family": "vins"}
        toggle_family(filters, "vins")
        assert "family" not in filters

    def test_switch(self):
        filters = {"family": "vins"}
        toggle_family(filters, "spiritueux")
        assert filters["family"] == "spiritueux"

    def test_clears_category_on_select(self):
        filters = {"family": "vins", "category": "rouge"}
        toggle_family(filters, "spiritueux")
        assert filters["family"] == "spiritueux"
        assert "category" not in filters

    def test_clears_category_on_deselect(self):
        filters = {"family": "vins", "category": "rouge"}
        toggle_family(filters, "vins")
        assert "family" not in filters
        assert "category" not in filters

    def test_preserves_price(self):
        filters = {"family": "vins", "price": "15-25"}
        toggle_family(filters, "spiritueux")
        assert filters["price"] == "15-25"


class TestTogglePrice:
    def test_select(self):
        filters = {}
        toggle_price(filters, "15-25")
        assert filters["price"] == "15-25"

    def test_deselect(self):
        filters = {"price": "15-25"}
        toggle_price(filters, "15-25")
        assert "price" not in filters

    def test_switch(self):
        filters = {"price": "15-25"}
        toggle_price(filters, "100-")
        assert filters["price"] == "100-"


# ── API params builder ────────────────────────────────────────


class TestBuildApiParams:
    # Sample grouped data for category resolution
    _grouped = {
        "rouge": ["Vin rouge"],
        "blanc": ["Vin blanc"],
        "bulles": ["Champagne", "Champagne rosé", "Vin mousseux", "Vin mousseux rosé"],
        "whisky": ["Whisky écossais", "Whisky américain"],
    }

    def test_search_no_filters(self):
        state = {"query": "merlot", "command": "search", "filters": {}}
        params = build_api_params(state, self._grouped)
        assert params["q"] == "merlot"
        assert "category" not in params
        assert "available" not in params

    def test_search_with_single_category(self):
        state = {"query": "wine", "command": "search", "filters": {"category": "rouge"}}
        params = build_api_params(state, self._grouped)
        assert params["category"] == ["Vin rouge"]

    def test_search_with_multi_category(self):
        """Bulles maps to multiple DB values as a list."""
        state = {"query": "wine", "command": "search", "filters": {"category": "bulles"}}
        params = build_api_params(state, self._grouped)
        assert isinstance(params["category"], list)
        assert "Vin mousseux" in params["category"]
        assert "Champagne" in params["category"]

    def test_category_expansion_uses_grouped_data(self):
        """Grouped data drives the DB values, not hardcoded lists."""
        state = {"query": None, "command": "search", "filters": {"category": "whisky"}}
        params = build_api_params(state, self._grouped)
        assert sorted(params["category"]) == ["Whisky américain", "Whisky écossais"]

    def test_unknown_category_omitted(self):
        """A group key not in grouped data produces no category param."""
        state = {"query": None, "command": "search", "filters": {"category": "sake"}}
        params = build_api_params(state, self._grouped)
        assert "category" not in params

    def test_search_with_price(self):
        state = {"query": "wine", "command": "search", "filters": {"price": "15-25"}}
        params = build_api_params(state, self._grouped)
        assert params["min_price"] == 15
        assert params["max_price"] == 25

    def test_search_with_open_price(self):
        state = {"query": "wine", "command": "search", "filters": {"price": "100-"}}
        params = build_api_params(state, self._grouped)
        assert params["min_price"] == 100
        assert "max_price" not in params

    def test_new_command_adds_available_and_sort(self):
        state = {"query": None, "command": "new", "filters": {}}
        params = build_api_params(state, self._grouped)
        assert params["available"] is True
        assert params["sort"] == "recent"
        assert "q" not in params

    def test_random_command_no_sort(self):
        state = {"query": None, "command": "random", "filters": {}}
        params = build_api_params(state, self._grouped)
        assert params["available"] is True
        assert "sort" not in params

    def test_fallback_when_grouped_is_none(self):
        """Without grouped data, falls back to group prefixes as DB values."""
        state = {"query": None, "command": "search", "filters": {"category": "rouge"}}
        params = build_api_params(state, None)
        assert params["category"] == ["Vin rouge"]

    def test_family_without_subgroup_expands_all_groups(self):
        """Family only → expand all child groups into one category list."""
        state = {"query": None, "command": "search", "filters": {"family": "vins"}}
        params = build_api_params(state, self._grouped)
        # vins has rouge, blanc, bulles in _grouped (rose/fortifie absent)
        expected = [
            "Vin rouge",
            "Vin blanc",
            "Champagne",
            "Champagne rosé",
            "Vin mousseux",
            "Vin mousseux rosé",
        ]
        assert sorted(params["category"]) == sorted(expected)

    def test_subgroup_takes_precedence_over_family(self):
        """When both family and category set, only the subgroup is expanded."""
        state = {
            "query": None,
            "command": "search",
            "filters": {"family": "vins", "category": "rouge"},
        }
        params = build_api_params(state, self._grouped)
        assert params["category"] == ["Vin rouge"]

    def test_unknown_family_no_category_param(self):
        state = {"query": None, "command": "search", "filters": {"family": "nonexistent"}}
        params = build_api_params(state, self._grouped)
        assert "category" not in params


# ── Filter callback handler ───────────────────────────────────


@pytest.fixture
def api():
    mock = AsyncMock()
    mock.list_products.return_value = {
        "products": [{"name": "Wine", "price": "10.00", "availability": True, "sku": "X"}],
        "total": 1,
        "page": 1,
        "per_page": 5,
        "pages": 1,
    }
    return mock


@pytest.fixture
def context(api):
    ctx = AsyncMock()
    ctx.bot_data = {
        "api": api,
        "category_groups": {
            "rouge": ["Vin rouge"],
            "blanc": ["Vin blanc"],
            "rose": ["Vin rosé"],
            "bulles": ["Champagne", "Vin mousseux"],
        },
    }
    ctx.user_data = {
        "search": {
            "query": "wine",
            "command": "search",
            "filters": {},
            "message_id": 1,
        }
    }
    return ctx


@pytest.fixture
def update():
    mock = AsyncMock()
    mock.callback_query.data = "f:cat:rouge"
    mock.callback_query.answer = AsyncMock()
    mock.callback_query.edit_message_text = AsyncMock()
    return mock


async def test_filter_toggles_category(update, context):
    update.callback_query.data = "f:cat:rouge"
    await filter_callback(update, context)

    assert context.user_data["search"]["filters"]["category"] == "rouge"
    call_kwargs = update.callback_query.edit_message_text.call_args.kwargs
    assert call_kwargs["parse_mode"] == "Markdown"
    assert call_kwargs["reply_markup"] is not None


async def test_filter_toggles_price(update, context):
    update.callback_query.data = "f:price:15-25"
    await filter_callback(update, context)

    assert context.user_data["search"]["filters"]["price"] == "15-25"


async def test_filter_toggles_family(update, context):
    update.callback_query.data = "f:fam:vins"
    await filter_callback(update, context)

    assert context.user_data["search"]["filters"]["family"] == "vins"


async def test_filter_clear(update, context):
    context.user_data["search"]["filters"] = {
        "family": "vins",
        "category": "rouge",
        "price": "15-25",
    }
    update.callback_query.data = "f:clear"
    await filter_callback(update, context)

    assert context.user_data["search"]["filters"] == {}


async def test_filter_expired_session(update, context):
    context.user_data = {}
    await filter_callback(update, context)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "expired" in text.lower()


async def test_filter_backend_unavailable(update, context, api):
    api.list_products.side_effect = BackendUnavailableError("down")
    await filter_callback(update, context)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "unavailable" in text.lower()


async def test_filter_backend_api_error(update, context, api):
    api.list_products.side_effect = BackendAPIError(500, "Internal Server Error")
    await filter_callback(update, context)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "unavailable" in text.lower()


# ── Random command filter path ───────────────────────────────


async def test_filter_random_uses_get_random_product(update, context, api):
    context.user_data["search"] = {
        "query": None,
        "command": "random",
        "filters": {},
    }
    api.get_random_product.return_value = {
        "name": "Wine",
        "price": "10.00",
        "availability": True,
        "sku": "X",
    }
    update.callback_query.data = "f:cat:rouge"
    await filter_callback(update, context)

    api.get_random_product.assert_called_once()
    api.list_products.assert_not_called()


async def test_filter_random_empty_catalog(update, context, api):
    context.user_data["search"] = {
        "query": None,
        "command": "random",
        "filters": {},
    }
    api.get_random_product.return_value = None
    update.callback_query.data = "f:cat:rouge"
    await filter_callback(update, context)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "no results" in text.lower()
