import dataclasses
import json
from dataclasses import dataclass
from html import unescape
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger


@dataclass(frozen=True)
class ProductData:
    """Structured product data extracted from a SAQ product page.

    Combines fields from two HTML sources:
    - JSON-LD script blocks (price, availability, rating, etc.)
    - HTML attribute list (region, grape, alcohol, etc.)
    """

    # Every field defaults to None — because out-of-stock or minimal products won't have all fields

    # Source metadata
    url: str | None = None  # Product page URL (passed from scraper)
    # JSON-LD fields
    name: str | None = None
    sku: str | None = None
    description: str | None = None
    category: str | None = None
    barcode: str | None = None
    image: str | None = None
    price: float | None = None
    currency: str | None = None
    availability: bool | None = None
    manufacturer: str | None = None
    rating: float | None = None
    review_count: int | None = None
    # HTML attribute fields
    country: str | None = None
    color: str | None = None
    size: str | None = None
    region: str | None = None
    appellation: str | None = None
    designation: str | None = None
    classification: str | None = None
    grape: str | None = None
    alcohol: str | None = None
    sugar: str | None = None
    producer: str | None = None
    saq_code: str | None = None
    cup_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict matching DB column names."""
        return dataclasses.asdict(self)


def parse_product(html: str, url: str) -> ProductData:
    """Parse a SAQ product page and return structured product data.

    Combines data from two sources in the HTML:
    - JSON-LD script blocks (price, availability, rating, etc.)
    - HTML attribute list (region, grape, alcohol, etc.)

    Args:
        html: Raw HTML string of a SAQ product page.
        url: Product page URL (for database record).

    Returns:
        ProductData with all available fields populated.
    """

    soup = BeautifulSoup(html, "lxml")  # lxml is the parser backend

    # JSON-LD: <script type="application/ld+json"> — price, availability, rating, image
    jsonld_fields = _parse_jsonld(soup, url)

    # HTML attrs: <ul class="list-attributs"> — region, grape, alcohol, sugar
    html_fields = _parse_html_attrs(soup)

    # The two dicts have disjoint keys so ** unpacking is safe
    return ProductData(url=url, **jsonld_fields, **html_fields)


# -------------- HELPERS -------------- #


def _parse_jsonld(soup: BeautifulSoup, url: str) -> dict[str, Any]:
    """Extract product fields from all JSON-LD Product blocks, merged.

    SAQ pages emit two Product blocks: a minimal one and a rich one.
    We merge all of them so later blocks fill in fields the first one lacks.
    """
    all_fields: dict[str, Any] = {}

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            logger.warning("Skipping unparseable JSON-LD block on {}", url)
            continue

        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue

        fields: dict[str, Any] = {}

        # String fields — apply html.unescape for encoded entities
        for key, jsonld_key in [
            ("name", "name"),
            ("sku", "sku"),
            ("description", "description"),
            ("category", "category"),
            ("barcode", "gtin12"),
        ]:
            value = data.get(jsonld_key)
            if isinstance(value, str) and value:
                fields[key] = unescape(value)

        # Image: strip query parameters
        image = data.get("image", "")
        if image:
            fields["image"] = image.split("?")[0]

        # Offers (price, currency, availability)
        offers = data.get("offers", {})
        if isinstance(offers, dict):
            price = offers.get("price")
            if price is not None:
                try:
                    fields["price"] = float(price)
                except (ValueError, TypeError):
                    logger.warning("Bad price value {!r} on {}", price, url)
            currency = offers.get("priceCurrency")
            if currency:
                fields["currency"] = currency
            availability = offers.get("availability")
            if availability is not None:
                fields["availability"] = "InStock" in str(availability)

        # Rating — SAQ uses French decimal commas ("4,4") in block 2
        rating_data = data.get("aggregateRating", {})
        if isinstance(rating_data, dict) and rating_data.get("ratingValue"):
            raw_rating = str(rating_data["ratingValue"]).replace(",", ".")
            try:
                fields["rating"] = float(raw_rating)
            except (ValueError, TypeError):
                logger.warning("Bad rating value {!r} on {}", rating_data["ratingValue"], url)
            review_count = rating_data.get("reviewCount")
            if review_count is not None:
                try:
                    fields["review_count"] = int(review_count)
                except (ValueError, TypeError):
                    logger.warning("Bad review_count value {!r} on {}", review_count, url)

        all_fields.update(fields)

    return all_fields


# Maps our English field names to the French labels that SAQ uses in their HTML
_LABEL_MAP: dict[str, str] = {
    "country": "Pays",
    "color": "Couleur",
    "size": "Format",
    "region": "Région",
    "appellation": "Appellation d'origine",
    "designation": "Désignation réglementée",
    "classification": "Classification",
    "grape": "Cépage",
    "alcohol": "Degré d'alcool",
    "sugar": "Taux de sucre",
    "producer": "Producteur",
    "saq_code": "Code SAQ",
    "cup_code": "Code CUP",
}


def _parse_html_attrs(soup: BeautifulSoup) -> dict[str, Any]:
    """Extract product fields from the HTML attributes list."""
    attr_list = soup.find("ul", class_="list-attributs")
    if not attr_list:
        return {}

    # Build label → value mapping from data-th attributes
    attrs: dict[str, str] = {}
    for strong in attr_list.find_all("strong", attrs={"data-th": True}):
        label = strong["data-th"]
        value = strong.get_text(strip=True)
        if value:
            attrs[label] = value

    # Map French labels to field names, skip missing ones
    return {field: attrs[label] for field, label in _LABEL_MAP.items() if label in attrs}
