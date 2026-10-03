"""Event loop compatibility for Windows + psycopg async.

psycopg's async support is incompatible with the default ProactorEventLoop
on Windows; the selector loop is required. Called from test bootstrap, the
seed script and (from M2) application startup.
"""

from __future__ import annotations

import asyncio
import sys


def ensure_compatible_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
