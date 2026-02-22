from __future__ import annotations

import sys

from loguru import logger

from core.config import settings


def configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if settings.debug else "INFO",
        backtrace=settings.debug,
        diagnose=settings.debug,
        enqueue=True,
    )
