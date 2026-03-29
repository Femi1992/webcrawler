"""Logging configuration for the crawler package.

Each module gets its own logger via logging.getLogger(__name__).
This file provides a single place to configure the package-level logger
and a helper to set up console output for CLI use.

Think of it like a PA system in a building:
- Each room (module) has its own mic (logger)
- They all feed into the same building PA (the root "crawler" logger)
- The building manager (main.py) decides how loud to turn the volume up
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under 'crawler'."""
    return logging.getLogger(name)


def configure(level: int = logging.INFO) -> None:
    """Configure the crawler package logger for CLI use.

    Sets up a single console handler with a clean format.
    Call this from main.py — library code should never call this directly.
    """
    logger = logging.getLogger("crawler")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
