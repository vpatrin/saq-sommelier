import sys

from loguru import logger


def setup_logging(service: str, level: str = "INFO") -> None:
    """Configure loguru for a service.

    Removes the default handler and adds one with a consistent format.
    Call this once at the top of each service's entrypoint.

    Args:
        service: Service name (e.g. "scraper", "backend") — appears in log output.
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
    """
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<level>{level:<8}</level> | {time:HH:mm:ss} | <cyan>{name}</cyan> | {message}",
    )
    logger.info("Logging initialized for {}", service)
