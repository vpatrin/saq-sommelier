from dataclasses import dataclass
from xml.etree import ElementTree

import httpx
from loguru import logger

from .config import settings

# XML namespace mapping — needed because sitemap XML uses xmlns namespace
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass(frozen=True)  # Makes instances immutable
class SitemapEntry:
    """A product URL entry from a SAQ sub-sitemap."""

    url: str
    lastmod: str | None = None  # Equivalent to Optional[str] from typing, but cleaner.


async def fetch_sitemap_index(client: httpx.AsyncClient) -> list[str]:
    """Fetch the SAQ sitemap index and return sub-sitemap URLs.

    Args:
        client: An httpx.AsyncClient configured with appropriate headers and timeout.

    Returns:
        List of sub-sitemap URLs (typically 2).
    """
    # Dependency injection of client in the function for reusability, control and reuse
    response = await client.get(settings.sitemap_index_url)
    response.raise_for_status()

    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as e:
        logger.error("Failed to parse sitemap index XML: {}", e)
        raise

    urls = []
    for sitemap in root.findall("sm:sitemap", _NS):  # finds all <sitemap> elements
        loc = sitemap.find("sm:loc", _NS)  # inside each <sitemap>, grab the <loc> child (the URL)
        if loc is not None and loc.text:  # skip if <loc> is missing or empty
            urls.append(loc.text.strip())

    return urls  # ["https://.../sitemap_product_1.xml", "https://.../sitemap_product_2.xml"]


async def fetch_sub_sitemap(client: httpx.AsyncClient, url: str) -> list[SitemapEntry]:
    """Fetch a sub-sitemap and return product URL entries.

    Args:
        client: An httpx.AsyncClient configured with appropriate headers and timeout.
        url: The sub-sitemap URL to fetch.

    Returns:
        List of SitemapEntry objects with url and optional lastmod.
    """
    response = await client.get(url)
    response.raise_for_status()

    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as e:
        logger.error("Failed to parse sub-sitemap XML from {}: {}", url, e)
        raise

    entries = []

    # url_el (not url) to avoid shadowing the function parameter
    for url_el in root.findall("sm:url", _NS):  # "sm:url" must match the actual XML tag <url>
        # <loc> = location (URL string), standard sitemap protocol tag
        loc = url_el.find("sm:loc", _NS)
        if loc is None or not loc.text:
            continue
        # Extracts last modification date if defined
        lastmod_el = url_el.find("sm:lastmod", _NS)
        lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else None

        entries.append(SitemapEntry(url=loc.text.strip(), lastmod=lastmod))

    return entries
