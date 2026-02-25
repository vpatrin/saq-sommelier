from typing import NamedTuple

# ── Category grouping ──────────────────────────────────────────
# Display concern only — groups 280+ raw SAQ categories into ~21 user-friendly groups,
# then bundles those groups into 3 families (Vins / Spiritueux / Autres) for a two-level
# filter keyboard. The backend API stays unchanged (filters by exact `category` strings
# via IN clause). Raw categories are discovered dynamically via /products/facets and
# matched by prefix.


class CategoryGroup(NamedTuple):
    label: str
    prefixes: tuple[str, ...]


class CategoryFamily(NamedTuple):
    label: str
    children: tuple[str, ...]  # keys into CATEGORY_GROUPS


#! Order matters — first match wins in group_facets(). Keep specific prefixes before generic ones.
CATEGORY_GROUPS: dict[str, CategoryGroup] = {
    "rouge": CategoryGroup("Vin rouge", ("Vin rouge",)),
    "blanc": CategoryGroup("Vin blanc", ("Vin blanc",)),
    "rose": CategoryGroup("Vin rosé", ("Vin rosé",)),
    "bulles": CategoryGroup("Mousseux", ("Champagne", "Vin mousseux")),
    "fortifie": CategoryGroup(
        "Vin fortifié",
        (
            "Porto",
            "Madère",
            "Xérès",
            "Marsala",
            "Sauternes",
            "Muscat",
            "Pineau",
            "Banyuls",
            "Maury",
            "Rivesaltes",
            "Macvin",
            "Floc",
            "Moscatel",
            "Montilla",
            "Vin de dessert",
            "Vin de glace",
            "Vin fortifié",
            "Vin doux naturel",
        ),
    ),
    "whisky": CategoryGroup("Whisky", ("Whisky", "Whiskey")),
    "rhum": CategoryGroup("Rhum", ("Rhum",)),
    "gin": CategoryGroup("Gin", ("Dry gin", "Genièvre")),
    "vodka": CategoryGroup("Vodka", ("Vodka",)),
    "tequila": CategoryGroup("Tequila", ("Téquila", "Mezcal", "Sotol")),
    "cognac": CategoryGroup("Cognac", ("Cognac", "Armagnac", "Brandy", "Calvados", "Pisco")),
    "liqueur": CategoryGroup("Liqueur", ("Liqueur",)),
    "biere": CategoryGroup("Bière", ("Bière",)),
    "cidre": CategoryGroup("Cidre", ("Cidre", "Poiré")),
    "eauxdevie": CategoryGroup(
        "Eau-de-vie",
        ("Eau-de-vie", "Eaux-de-vie", "Grappa", "Kirsch", "Poire Williams", "Marc "),
    ),
    "aperitif": CategoryGroup(
        "Apéritif",
        ("Vermouth", "Apéritif", "Vin apéritif", "Alcool anisé", "Absinthe", "Anisette"),
    ),
    "cocktail": CategoryGroup("Cocktails", ("Cocktail", "Cooler")),
    "boisson": CategoryGroup("Boissons", ("Boisson",)),
    "sake": CategoryGroup("Saké", ("Saké", "Baijiu")),
    "hydromel": CategoryGroup("Hydromel", ("Hydromel",)),
    "autre": CategoryGroup("Autre", ()),  # catch-all — must be last
}

CATEGORY_ROW_SIZE = 3  # buttons per keyboard row

# ── Category families ─────────────────────────────────────────
# Two-level hierarchy: 3 families → subgroups. Every CATEGORY_GROUPS key appears in
# exactly one family. The "autre" catch-all lives in "autres".

CATEGORY_FAMILIES: dict[str, CategoryFamily] = {
    "vins": CategoryFamily("🍷 Vins", ("rouge", "blanc", "rose", "bulles", "fortifie")),
    "spiritueux": CategoryFamily(
        "🥃 Spiritueux",
        ("whisky", "rhum", "gin", "vodka", "tequila", "cognac", "liqueur", "eauxdevie", "aperitif"),
    ),
    "autres": CategoryFamily(
        "🍺 Autres",
        ("biere", "cidre", "cocktail", "boisson", "sake", "hydromel", "autre"),
    ),
}


def group_facets(raw_categories: list[str]) -> dict[str, list[str]]:
    """Group raw DB categories into user-friendly groups using prefix matching.

    Returns {group_key: [matching raw category strings]}.
    Unmatched categories land in "autre".
    """
    grouped: dict[str, list[str]] = {}

    for cat in raw_categories:
        matched = False
        for key, group in CATEGORY_GROUPS.items():
            if key == "autre":
                continue
            if any(cat.startswith(prefix) for prefix in group.prefixes):
                grouped.setdefault(key, []).append(cat)
                matched = True
                break
        if not matched:
            grouped.setdefault("autre", []).append(cat)

    return grouped


def expand_group(group_key: str, grouped: dict[str, list[str]] | None) -> list[str]:
    """Return raw DB categories for a group key.

    Falls back to the group's prefixes only when grouped data is entirely
    unavailable (None — e.g. facets fetch failed at startup).
    When grouped is a dict but the key is absent, returns [] (no products in that group).
    """
    if grouped is not None:
        return grouped.get(group_key, [])

    # Best-effort fallback — prefixes are often valid category names themselves
    group = CATEGORY_GROUPS.get(group_key)
    return list(group.prefixes) if group else []


def expand_family(family_key: str, grouped: dict[str, list[str]] | None) -> list[str]:
    """Return ALL raw DB categories for every group in a family.

    Used when a family is selected but no specific subgroup — the API should
    filter to all categories within that family (e.g. all wine types).
    Delegates to expand_group() per child, inheriting the None fallback.
    """
    family = CATEGORY_FAMILIES.get(family_key)
    if not family:
        return []

    db_values: list[str] = []
    for group_key in family.children:
        db_values.extend(expand_group(group_key, grouped))
    return db_values
