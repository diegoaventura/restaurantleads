"""Application logging setup.

Single format across the app; level from LOG_LEVEL (see .env.example).
Secrets, passwords and message content must never be logged.
"""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def setup_logging(level: str) -> None:
    logging.basicConfig(level=_resolve_level(level), format=LOG_FORMAT)
    # Quieter third-party loggers.
    for name in ("uvicorn.error",):
        logging.getLogger(name).setLevel(_resolve_level(level))


def _resolve_level(level: str) -> int:
    return getattr(logging, level.upper(), logging.INFO)
