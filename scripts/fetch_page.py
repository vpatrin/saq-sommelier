#!/usr/bin/env python3
"""Fetch a SAQ product page and extract interesting data."""

import json
import sys

import httpx
from bs4 import BeautifulSoup

UA = "SAQSommelier/0.1.0 (personal project; https://github.com/vpatrin/saq-sommelier)"


def parse_jsonld(soup: BeautifulSoup) -> dict:
    """Extract fields from JSON-LD Product blocks."""
    product = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if not isinstance(data, dict) or data.get("@type") != "Product":
                continue

            product["name"] = data.get("name")
            product["sku"] = data.get("sku")
            product["description"] = data.get("description")
            product["category"] = data.get("category")
            product["country"] = data.get("countryOfOrigin")
            product["barcode"] = data.get("gtin12")
            product["color"] = data.get("color")
            product["size"] = data.get("size")

            image = data.get("image", "")
            if image:
                product["image"] = image.split("?")[0]

            offers = data.get("offers", {})
            product["price"] = offers.get("price")
            product["currency"] = offers.get("priceCurrency")
            product["availability"] = "InStock" in str(offers.get("availability", ""))

            manufacturer = data.get("manufacturer", {})
            if isinstance(manufacturer, dict):
                product["manufacturer"] = manufacturer.get("name")

            rating = data.get("aggregateRating", {})
            if isinstance(rating, dict) and rating.get("ratingValue"):
                product["rating"] = rating.get("ratingValue")
                product["review_count"] = rating.get("reviewCount")

        except (json.JSONDecodeError, TypeError):
            pass

    return product


def parse_html_attrs(soup: BeautifulSoup) -> dict:
    """Extract fields from the HTML attributes list."""
    product = {}
    attr_list = soup.find("ul", class_="list-attributs")
    if not attr_list:
        return product

    attrs = {}
    for strong in attr_list.find_all("strong", attrs={"data-th": True}):
        label = strong["data-th"]
        value = strong.get_text(strip=True)
        if value:
            attrs[label] = value

    product["region"] = attrs.get("Région")
    product["appellation"] = attrs.get("Appellation d'origine")
    product["designation"] = attrs.get("Désignation réglementée")
    product["classification"] = attrs.get("Classification")
    product["grape"] = attrs.get("Cépage")
    product["alcohol"] = attrs.get("Degré d'alcool")
    product["sugar"] = attrs.get("Taux de sucre")
    product["producer"] = attrs.get("Producteur")
    product["saq_code"] = attrs.get("Code SAQ")
    product["cup_code"] = attrs.get("Code CUP")

    return product


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/fetch_page.py https://www.saq.com/fr/10327701")
        sys.exit(1)

    url = sys.argv[1]
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    product = parse_jsonld(soup)
    product.update(parse_html_attrs(soup))

    # Remove None values
    product = {k: v for k, v in product.items() if v is not None}

    print(json.dumps(product, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
