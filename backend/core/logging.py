from __future__ import annotations

import logging
import sys

from loguru import logger

from core.config import settings


class _InterceptHandler(logging.Handler):
    """Bridge stdlib logging (uvicorn, fastapi, etc.) into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # type: ignore[assignment]
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if settings.debug else "INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        backtrace=settings.debug,
        diagnose=settings.debug,
        colorize=True,
    )
    # Route all stdlib loggers (uvicorn, fastapi, openai, etc.) through loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        _log = logging.getLogger(name)
        _log.handlers = [_InterceptHandler()]
        _log.propagate = False
