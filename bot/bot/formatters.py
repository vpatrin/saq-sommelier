from datetime import datetime
from typing import Any

from bot.config import SAQ_BASE_URL


def format_product_line(product: dict[str, Any], index: int) -> str:
    """
    Format a single product for Telegram Markdown display.
    Output example:
    1. Château Margaux — 89$ ✅
    Where "Château Margaux" links to https://www.saq.com/fr/15483332
    """

    name = product.get("name") or "Unknown"
    price = product.get("price")
    available = product.get("availability")
    sku = product.get("sku", "")

    price_str = f"{price}$" if price is not None else "N/A"
    status = "\u2705" if available else "\u274c"

    url = f"{SAQ_BASE_URL}/{sku}"
    return f"{index}. [{name}]({url}) \u2014 {price_str} {status}"


def format_product_list(data: dict[str, Any]) -> str:
    """Format a paginated product response for Telegram.
    Output example:
    *12 results* (showing 5)
    1. Château Margaux — 89$ ✅
    2. Mouton Rothschild — 250$ ✅
    3. Some Cheap Wine — 15$ ❌
    """
    products = data.get("products", [])
    total = data.get("total", 0)

    if not products:
        return "No results found."

    lines = [format_product_line(p, i + 1) for i, p in enumerate(products)]
    body = "\n\n".join(lines)

    header = f"*{total} result{'s' if total != 1 else ''}*"
    current_page = data["page"]
    total_pages = data["pages"]
    if total_pages > 1:
        header += f" — page {current_page}/{total_pages}"

    return f"{header}\n\n{body}"


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
