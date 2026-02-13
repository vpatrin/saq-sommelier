#!/usr/bin/env python3
"""Explore SAQ sitemap structure: list sub-sitemaps and count product URLs."""

import sys
from xml.etree import ElementTree

import httpx

SITEMAP_INDEX = "https://www.saq.com/media/sitemaps/fr/sitemap_product.xml"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
UA = "SAQSommelier/0.1.0 (personal project; https://github.com/vpatrin/saq-sommelier)"


def main():
    client = httpx.Client(headers={"User-Agent": UA}, timeout=30)

    # Fetch sitemap index
    print("=== SAQ Sitemap Explorer ===\n")
    print("Fetching sitemap index...")
    resp = client.get(SITEMAP_INDEX)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)

    # Extract sub-sitemaps
    sitemaps = []
    for sitemap in root.findall("sm:sitemap", NS):
        loc = sitemap.find("sm:loc", NS)
        lastmod = sitemap.find("sm:lastmod", NS)
        if loc is not None and loc.text:
            sitemaps.append({
                "url": loc.text,
                "lastmod": lastmod.text if lastmod is not None else None,
            })

    print(f"Found {len(sitemaps)} sub-sitemaps:\n")
    for s in sitemaps:
        print(f"  {s['url']}  (lastmod: {s['lastmod']})")

    # Count URLs per sub-sitemap
    print()
    total = 0
    for s in sitemaps:
        print(f"Fetching {s['url']}...")
        resp = client.get(s["url"])
        resp.raise_for_status()
        sub_root = ElementTree.fromstring(resp.content)
        count = len(sub_root.findall("sm:url", NS))
        print(f"  → {count} product URLs")
        total += count

    print(f"\nTotal products: {total}")

    # Show sample URLs from first sub-sitemap
    print("\n=== Sample URLs (first 100) ===\n")
    resp = client.get(sitemaps[0]["url"])
    sub_root = ElementTree.fromstring(resp.content)
    for url_el in sub_root.findall("sm:url", NS)[:100]:
        loc = url_el.find("sm:loc", NS)
        lastmod = url_el.find("sm:lastmod", NS)
        if loc is not None:
            lm = lastmod.text if lastmod is not None else "none"
            print(f"  {loc.text}  (lastmod: {lm})")


if __name__ == "__main__":
    main()
