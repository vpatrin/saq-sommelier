from typing import Any


def format_product_line(product: dict[str, Any], index: int) -> str:
    """
    Format a single product for Telegram Markdown display.
    Output example:
    1. Château Margaux — 89$ ✅
    Where "Château Margaux" links to https://www.saq.com/en/15483332
    """

    name = product.get("name") or "Unknown"
    price = product.get("price")
    available = product.get("availability")
    sku = product.get("sku", "")

    price_str = f"{price}$" if price is not None else "N/A"
    status = "\u2705" if available else "\u274c"

    url = f"https://www.saq.com/en/{sku}"
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
    if total > len(products):
        header += f" (showing {len(products)})"

    return f"{header}\n\n{body}"
