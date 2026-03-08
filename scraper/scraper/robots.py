from urllib.robotparser import RobotFileParser

from loguru import logger


def load_robots(url: str) -> RobotFileParser:
    """Fetch and parse robots.txt. Called once at scraper startup."""
    rp = RobotFileParser()
    rp.set_url(url)
    rp.read()
    logger.info("Loaded robots.txt from {}", url)
    return rp


def is_allowed(rp: RobotFileParser, url: str, user_agent: str = "*") -> bool:
    """Check if a URL is allowed by robots.txt rules."""
    return rp.can_fetch(user_agent, url)
