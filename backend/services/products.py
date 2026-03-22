import asyncio
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.exceptions import NotFoundError
from backend.repositories.products import (
    count,
    find_by_sku,
    find_page,
    find_random,
    get_distinct_values,
    get_distinct_values_by_count,
    get_price_range,
)
from backend.schemas.product import (
    CategoryFamilyOut,
    CategoryGroupOut,
    CountryFacet,
    FacetsOut,
    PaginatedOut,
    PriceRange,
    ProductOut,
)
from core.categories import CATEGORY_FAMILIES, CATEGORY_GROUPS, group_facets
from core.db.models import Product

_GROUP_ORDER = {k: i for i, k in enumerate(CATEGORY_GROUPS)}


async def get_product(db: AsyncSession, sku: str) -> ProductOut:
    """Fetch a single product by SKU. Raises NotFoundError if not found."""
    product = await find_by_sku(db, sku)
    if product is None:
        raise NotFoundError("Product", sku)
    return ProductOut.model_validate(product)


async def list_products(
    db: AsyncSession,
    limit: int,
    offset: int,
    *,
    sort: str | None = None,
    q: str | None = None,
    category: list[str] | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
    in_stores: list[str] | None = None,
    wine_scope: bool = False,
) -> PaginatedOut:
    """Fetch a paginated list of products, optionally filtered and sorted."""
    filters = dict(
        q=q,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
        in_stores=in_stores,
        wine_scope=wine_scope,
    )
    total = await count(db, **filters)
    rows = await find_page(db, offset, limit, sort=sort, **filters)

    return PaginatedOut(
        products=[ProductOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_random_product(
    db: AsyncSession,
    *,
    category: list[str] | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
    in_stores: list[str] | None = None,
    wine_scope: bool = False,
) -> ProductOut:
    """Fetch a single random product matching filters. Raises NotFoundError if none."""
    product = await find_random(
        db,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
        in_stores=in_stores,
        wine_scope=wine_scope,
    )
    if product is None:
        raise NotFoundError("Product", "no product matches the given filters")
    return ProductOut.model_validate(product)


async def get_facets(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    category: list[str] | None = None,
    available: bool | None = None,
    in_stores: list[str] | None = None,
    wine_scope: bool = False,
) -> FacetsOut:
    """Fetch distinct filter values and price range for active products."""
    availability_filters = dict(
        available=available,
        in_stores=in_stores,
        wine_scope=wine_scope,
    )

    # Each query gets its own session — asyncio.gather needs independent connections.
    async def _run(fn, *args, **kwargs):
        async with session_factory() as s:
            return await fn(s, *args, **kwargs)

    #! Order must match destructuring — tests mock by position
    # * Categories skip availability filters — chip list shows all categories
    # regardless of online/in-store toggles.
    categories, country_rows, regions, grapes, price_result = await asyncio.gather(
        _run(get_distinct_values, Product.category, wine_scope=wine_scope),
        _run(
            get_distinct_values_by_count, Product.country, category=category, **availability_filters
        ),
        _run(get_distinct_values, Product.region, category=category, **availability_filters),
        _run(get_distinct_values, Product.grape, category=category, **availability_filters),
        _run(get_price_range, category=category, **availability_filters),
    )
    countries = [CountryFacet(name=name, count=cnt) for name, cnt in country_rows]

    # Build grouped categories — preserves CATEGORY_GROUPS definition order
    grouped = group_facets(categories)
    grouped_categories = [
        CategoryGroupOut(key=key, label=CATEGORY_GROUPS[key].label, categories=raw_cats)
        for key, raw_cats in sorted(
            grouped.items(),
            key=lambda item: _GROUP_ORDER.get(item[0], len(_GROUP_ORDER)),
        )
    ]

    # Build category families — only include families that have at least one populated group
    category_families = [
        CategoryFamilyOut(
            key=fam_key,
            label=fam.label,
            children=[gk for gk in fam.children if gk in grouped],
        )
        for fam_key, fam in CATEGORY_FAMILIES.items()
        if any(gk in grouped for gk in fam.children)
    ]

    return FacetsOut(
        categories=categories,
        grouped_categories=grouped_categories,
        category_families=category_families,
        countries=countries,
        regions=regions,
        grapes=grapes,
        price_range=PriceRange(min=price_result[0], max=price_result[1]) if price_result else None,
    )
