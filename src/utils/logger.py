"""
Centralized logging configuration for Prompt Island.
Call setup_logging() once at application startup (e.g., in the Game Engine entry point).
"""

from __future__ import annotations

import logging
import os
import sys


def setup_logging(level: int | None = None) -> None:
    """
    Configure the root logger for the entire Prompt Island engine.

    Log level is read from the LOG_LEVEL environment variable, falling back
    to INFO if not set. The caller can override with an explicit `level` int.
    """
    if level is None:
        env_level = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,  # Override any previously configured root handlers
    )

    # Silence overly verbose third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
