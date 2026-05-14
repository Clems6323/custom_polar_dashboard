"""Structured logging configuration for the platform.

Call :func:`configure_logging` once at application start-up (e.g. in the
Streamlit entry-point or the CLI scripts).  Individual modules should obtain
loggers via ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO", *, debug: bool = False) -> None:
    """Configure root logging with a consistent format.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        debug: When True, forces DEBUG level regardless of *level*.
    """
    effective_level = logging.DEBUG if debug else getattr(logging, level.upper(), logging.INFO)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(effective_level)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(effective_level)
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers at INFO unless debugging
    if not debug:
        for noisy in ("httpx", "httpcore", "bleak", "duckdb"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
