from unittest.mock import patch
from urllib.robotparser import RobotFileParser

import pytest

from src.robots import is_allowed, load_robots

# SAQ-like robots.txt rules for testing (no network needed)
_SAQ_RULES = [
    "User-agent: *",
    "Disallow: /catalog/product/view/",
    "Disallow: /catalogsearch/",
    "Disallow: /checkout/",
    "Disallow: /customer/",
    "Disallow: /wishlist/",
]


def _make_parser(rules: list[str] | None = None) -> RobotFileParser:
    """Build a RobotFileParser from rule strings — no network."""
    rp = RobotFileParser()
    rp.parse(rules or _SAQ_RULES)
    return rp


class TestIsAllowed:
    """is_allowed() — checks URLs against parsed robots.txt rules."""

    def test_product_url_allowed(self) -> None:
        rp = _make_parser()
        assert is_allowed(rp, "https://www.saq.com/en/14789") is True

    def test_catalog_product_view_blocked(self) -> None:
        rp = _make_parser()
        assert is_allowed(rp, "https://www.saq.com/catalog/product/view/id/123") is False

    def test_catalogsearch_blocked(self) -> None:
        rp = _make_parser()
        assert is_allowed(rp, "https://www.saq.com/catalogsearch/result/?q=wine") is False

    def test_checkout_blocked(self) -> None:
        rp = _make_parser()
        assert is_allowed(rp, "https://www.saq.com/checkout/cart") is False

    def test_customer_blocked(self) -> None:
        rp = _make_parser()
        assert is_allowed(rp, "https://www.saq.com/customer/account") is False

    def test_wishlist_blocked(self) -> None:
        rp = _make_parser()
        assert is_allowed(rp, "https://www.saq.com/wishlist/index/add/product/42") is False

    def test_respects_user_agent_rules(self) -> None:
        """User-agent-specific rules are respected."""
        rp = _make_parser(
            [
                "User-agent: BadBot",
                "Disallow: /",
                "",
                "User-agent: *",
                "Disallow: /admin/",
            ]
        )
        # BadBot is blocked everywhere
        assert is_allowed(rp, "https://www.saq.com/fr/14789", "BadBot") is False
        # Other agents only blocked from /admin/
        assert is_allowed(rp, "https://www.saq.com/fr/14789", "GoodBot") is True
        assert is_allowed(rp, "https://www.saq.com/admin/", "GoodBot") is False


class TestLoadRobots:
    """load_robots() — fetches and parses robots.txt."""

    def test_returns_robot_file_parser(self) -> None:
        with patch.object(RobotFileParser, "read"):
            rp = load_robots("https://www.saq.com/robots.txt")
        assert isinstance(rp, RobotFileParser)

    def test_raises_on_network_error(self) -> None:
        with (
            patch.object(RobotFileParser, "read", side_effect=OSError("network down")),
            pytest.raises(OSError),
        ):
            load_robots("https://www.saq.com/robots.txt")
