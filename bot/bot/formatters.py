from datetime import datetime
from typing import Any

from bot.config import SAQ_BASE_URL


def format_product_line(product: dict[str, Any], index: int) -> str:
    """Format a single product for Telegram Markdown display.
    Output example:
    1. Château Margaux — 89$ ✅
    Where "Château Margaux" links to https://www.saq.com/fr/15483332
    """

    name = product.get("name") or "Unknown"
    price = product.get("price")
    available = product.get("online_availability")
    sku = product.get("sku", "")

    price_str = f"{price}$" if price is not None else "N/A"
    status = "\u2705" if available else "\u274c"

    url = f"{SAQ_BASE_URL}/{sku}"
    return f"{index}. [{name}]({url}) \u2014 {price_str} {status}"


def format_recommendations(data: dict[str, Any]) -> str:
    """Format recommendation results for Telegram — rich cards for curated results."""
    products = data.get("products", [])

    if not products:
        return "No recommendations found for this query. Try rephrasing?"

    lines = []
    for i, p in enumerate(products, 1):
        name = p.get("name") or "Unknown"
        sku = p.get("sku", "")
        price = p.get("price")
        price_str = f"{price}$" if price is not None else "N/A"
        available = p.get("online_availability")
        status = "\u2705" if available else "\u274c"
        url = f"{SAQ_BASE_URL}/{sku}"

        line = f"{i}. [{name}]({url}) \u2014 {price_str} {status}"

        # Line 2: grape · region, country (deduplicated)
        origin_parts: list[str] = []
        grape = p.get("grape") or ""
        if grape:
            origin_parts.append(grape)
        region = p.get("region")
        country = p.get("country")
        location = _format_origin(region, country)
        if location:
            origin_parts.append(location)
        if origin_parts:
            line += f"\n    _{' · '.join(origin_parts)}_"

        # Line 3: taste_tag · vintage
        detail_parts: list[str] = []
        if p.get("taste_tag"):
            detail_parts.append(p["taste_tag"])
        if p.get("vintage"):
            detail_parts.append(str(p["vintage"]))
        if detail_parts:
            line += f"\n    _{' · '.join(detail_parts)}_"

        lines.append(line)

    return "\n\n".join(lines)


def _format_origin(region: str | None, country: str | None) -> str:
    """Deduplicate region/country — handles SAQ's 'Parent, Sub' region format."""
    if region:
        # Dedup "Bourgogne, Bourgogne" → "Bourgogne" (SAQ quirk: sub-region = parent)
        parts = [p.strip() for p in region.split(",")]
        if len(parts) == 2 and parts[0].lower() == parts[1].lower():
            region = parts[0]
    if region and country:
        if region.lower() == country.lower():
            return country
        return f"{region}, {country}"
    return region or country or ""


def _format_watch_line(entry: dict[str, Any], index: int) -> str:
    """Format a single watch entry (WatchWithProduct) for Telegram."""
    watch = entry["watch"]
    product = entry.get("product")

    if product:
        line = format_product_line(product, index)
    else:
        line = f"{index}. `{watch['sku']}` \u2014 product no longer available"

    created_at = watch.get("created_at")
    if created_at:
        dt = datetime.fromisoformat(created_at)
        line += f" _(since {dt.strftime('%b')} {dt.day})_"

    return line


def format_watch_list(watches: list[dict[str, Any]]) -> str:
    """Format the /alerts output — list of watched products."""
    if not watches:
        return "You're not watching any wines yet.\nUse /watch `<sku>` to start."

    header = f"*{len(watches)} watched wine{'s' if len(watches) != 1 else ''}*"
    lines = [_format_watch_line(entry, i + 1) for i, entry in enumerate(watches)]
    return f"{header}\n\n{'\n\n'.join(lines)}"


def format_delist_notification(notif: dict[str, Any]) -> str:
    """Format a delist alert — product removed from SAQ's catalog."""
    sku = notif["sku"]
    name = notif.get("product_name") or sku
    url = f"{SAQ_BASE_URL}/{sku}"
    return (
        f"\U0001f6ab *{name}* has been removed from SAQ's catalog.\n"
        f"Your watch has been removed — this product is no longer listed on SAQ.\n"
        f"\U0001f517 [saq.com/{sku}]({url})"
    )


def format_stock_notification(notifications: list[dict[str, Any]]) -> str:
    """Format a grouped stock alert — one message per (user, product, direction)."""
    first = notifications[0]
    sku = first["sku"]
    name = first.get("product_name") or sku
    url = f"{SAQ_BASE_URL}/{sku}"
    is_restock = first["available"]
    online_available = first.get("online_available")

    stores: list[str] = []
    has_online_event = False
    for n in notifications:
        loc = _event_location(n)
        if loc:
            stores.append(loc)
        else:
            has_online_event = True

    # Online-only — no bullet list
    if not stores and has_online_event:
        verb = "Back in stock online" if is_restock else "Out of stock online"
        emoji = "\U0001f377" if is_restock else "\U0001f4e6"
        return f"{emoji} {verb}: [{name}]({url})"

    emoji = "\U0001f377" if is_restock else "\U0001f4e6"
    verb = "Back in stock" if is_restock else "Out of stock"
    lines = [f"{emoji} {verb}: [{name}]({url})"]

    if has_online_event:
        lines.append("  \u2022 Online")
    for loc in stores:
        lines.append(f"  \u2022 {loc}")

    # Online availability hint when no online event in the group
    if not has_online_event and online_available is True:
        hint = "Also available online" if is_restock else "Still available online"
        lines.append(f"\U0001f310 {hint}")

    return "\n".join(lines)


def _event_location(n: dict[str, Any]) -> str | None:
    """Return store name for store events, None for online events."""
    if n.get("saq_store_id") is None:
        return None
    return n.get("store_name") or n["saq_store_id"]


# ── Stores ────────────────────────────────────────────────────


def format_user_stores(stores: list[dict[str, Any]]) -> str:
    """Format the /mystores summary — list of saved stores."""
    if not stores:
        return "\U0001f4cd *My stores* (0 saved)\n\nNo stores saved yet."

    count = len(stores)
    header = f"\U0001f4cd *{count} saved store{'s' if count != 1 else ''}*"
    lines = []
    for i, pref in enumerate(stores, 1):
        store = pref.get("store", pref)
        name = store.get("name") or "Unknown"
        city = store.get("city", "")
        lines.append(f"{i}. {name} — {city}")

    body = "\n".join(lines)
    return f"{header}\n\n{body}"
