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


def format_restock_notification(notification: dict[str, Any]) -> str:
    """Format a proactive restock alert sent by the bot."""
    sku = notification["sku"]
    name = notification.get("product_name") or sku
    url = f"{SAQ_BASE_URL}/{sku}"
    store_name = notification.get("store_name")
    if store_name:
        return f"\U0001f377 Back in stock at *{store_name}*: [{name}]({url})"
    return f"\U0001f377 Back in stock: [{name}]({url})"


def format_destock_notification(notification: dict[str, Any]) -> str:
    """Format a proactive destock alert sent by the bot."""
    sku = notification["sku"]
    name = notification.get("product_name") or sku
    url = f"{SAQ_BASE_URL}/{sku}"
    store_name = notification.get("store_name")
    if store_name:
        return f"\U0001f4e6 Out of stock at *{store_name}*: [{name}]({url})"
    return f"\U0001f4e6 Out of stock: [{name}]({url})"


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
