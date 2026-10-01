"""Logging setup. `setup_logging()` is called once at process startup
(main()); every other module just calls `get_logger(__name__)`, which gives
it a logger named after its own module path (e.g. "virtual_plc.plc.scan")
instead of a hand-picked string.
"""

from __future__ import annotations

import logging

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
