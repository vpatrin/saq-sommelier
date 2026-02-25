from bot.categories import (
    CATEGORY_FAMILIES,
    CATEGORY_GROUPS,
    expand_family,
    expand_group,
    group_facets,
)


class TestGroupFacets:
    """group_facets() — prefix matching + 'autre' fallback."""

    def test_groups_wine_categories(self) -> None:
        raw = ["Vin rouge", "Vin blanc", "Vin rosé"]
        grouped = group_facets(raw)
        assert grouped["rouge"] == ["Vin rouge"]
        assert grouped["blanc"] == ["Vin blanc"]
        assert grouped["rose"] == ["Vin rosé"]

    def test_groups_subcategories_by_prefix(self) -> None:
        raw = ["Whisky écossais", "Whisky américain", "Whiskey irlandais"]
        grouped = group_facets(raw)
        assert sorted(grouped["whisky"]) == sorted(raw)

    def test_bulles_groups_champagne_and_mousseux(self) -> None:
        raw = ["Champagne", "Champagne rosé", "Vin mousseux", "Vin mousseux rosé"]
        grouped = group_facets(raw)
        assert sorted(grouped["bulles"]) == sorted(raw)

    def test_fortifie_groups_multiple_prefixes(self) -> None:
        raw = ["Porto blanc", "Porto rouge", "Madère", "Xérès"]
        grouped = group_facets(raw)
        assert sorted(grouped["fortifie"]) == sorted(raw)

    def test_unmatched_goes_to_autre(self) -> None:
        raw = ["Something completely unknown"]
        grouped = group_facets(raw)
        assert grouped["autre"] == ["Something completely unknown"]
        assert len(grouped) == 1

    def test_empty_input(self) -> None:
        assert group_facets([]) == {}

    def test_mixed_known_and_unknown(self) -> None:
        raw = ["Vin rouge", "Bière artisanale", "Mystery category"]
        grouped = group_facets(raw)
        assert grouped["rouge"] == ["Vin rouge"]
        assert grouped["biere"] == ["Bière artisanale"]
        assert grouped["autre"] == ["Mystery category"]

    def test_first_match_wins(self) -> None:
        """A category matching multiple group prefixes goes to the first match."""
        # "Vin de dessert" matches "fortifie" prefixes — verify it doesn't also appear elsewhere
        raw = ["Vin de dessert"]
        grouped = group_facets(raw)
        assert grouped["fortifie"] == ["Vin de dessert"]
        assert len(grouped) == 1

    def test_all_groups_have_entries_in_mapping(self) -> None:
        """Every group key in CATEGORY_GROUPS is a valid dict key."""
        assert "autre" in CATEGORY_GROUPS
        # "autre" has no prefixes — it's the catch-all
        assert CATEGORY_GROUPS["autre"].prefixes == ()


class TestExpandGroup:
    """expand_group() — lookup + fallback to prefixes."""

    def test_returns_raw_categories_from_grouped(self) -> None:
        grouped = {"rouge": ["Vin rouge"], "whisky": ["Whisky écossais", "Whisky canadien"]}
        assert expand_group("whisky", grouped) == ["Whisky écossais", "Whisky canadien"]

    def test_returns_empty_for_missing_group(self) -> None:
        grouped = {"rouge": ["Vin rouge"]}
        assert expand_group("whisky", grouped) == []

    def test_falls_back_to_prefixes_when_grouped_is_none(self) -> None:
        result = expand_group("whisky", None)
        assert result == ["Whisky", "Whiskey"]

    def test_empty_grouped_returns_empty(self) -> None:
        """Empty dict means facets returned no categories — no fallback."""
        assert expand_group("whisky", {}) == []

    def test_fallback_returns_empty_for_unknown_key(self) -> None:
        assert expand_group("nonexistent", None) == []

    def test_autre_fallback_returns_empty(self) -> None:
        """'autre' has no prefixes, so fallback returns empty list."""
        assert expand_group("autre", None) == []


class TestExpandFamily:
    """expand_family() — aggregates all groups in a family."""

    _grouped = {
        "rouge": ["Vin rouge"],
        "blanc": ["Vin blanc"],
        "rose": ["Vin rosé"],
        "bulles": ["Champagne", "Vin mousseux"],
        "fortifie": ["Porto blanc"],
        "whisky": ["Whisky écossais"],
        "biere": ["Bière artisanale"],
    }

    def test_expands_all_wine_groups(self) -> None:
        result = expand_family("vins", self._grouped)
        assert sorted(result) == sorted(
            ["Vin rouge", "Vin blanc", "Vin rosé", "Champagne", "Vin mousseux", "Porto blanc"]
        )

    def test_skips_empty_children(self) -> None:
        """Groups not in grouped data contribute nothing (e.g. rhum not in _grouped)."""
        result = expand_family("spiritueux", self._grouped)
        assert result == ["Whisky écossais"]

    def test_unknown_family_returns_empty(self) -> None:
        assert expand_family("nonexistent", self._grouped) == []

    def test_fallback_when_grouped_is_none(self) -> None:
        result = expand_family("vins", None)
        # Falls back to prefixes for each child group
        assert "Vin rouge" in result
        assert "Champagne" in result
        assert "Porto" in result

    def test_empty_grouped_returns_empty(self) -> None:
        assert expand_family("vins", {}) == []


class TestCategoryFamilies:
    """CATEGORY_FAMILIES mapping integrity."""

    def test_every_group_in_exactly_one_family(self) -> None:
        """Every CATEGORY_GROUPS key appears in exactly one family."""
        all_children = []
        for family in CATEGORY_FAMILIES.values():
            all_children.extend(family.children)

        assert sorted(all_children) == sorted(CATEGORY_GROUPS.keys())
        assert len(all_children) == len(set(all_children)), "duplicate child found"

    def test_no_orphan_children(self) -> None:
        """Every child key in CATEGORY_FAMILIES exists in CATEGORY_GROUPS."""
        for family in CATEGORY_FAMILIES.values():
            for child in family.children:
                assert child in CATEGORY_GROUPS, f"{child} not in CATEGORY_GROUPS"

    def test_three_families(self) -> None:
        assert list(CATEGORY_FAMILIES.keys()) == ["vins", "spiritueux", "autres"]
