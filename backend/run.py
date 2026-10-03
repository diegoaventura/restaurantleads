"""Development server launcher.

Usage (from backend/):
    python run.py

Why not `uvicorn app.main:app` directly? On Windows, uvicorn (>=0.36)
forces a ProactorEventLoop via its loop factory, which psycopg async
rejects. With `loop="none"` uvicorn falls back to the default event loop
policy — and the WindowsSelectorEventLoopPolicy set below makes it
compatible. On Linux/macOS this is a no-op.
"""

from __future__ import annotations

from app.core.eventloop import ensure_compatible_event_loop

ensure_compatible_event_loop()

import uvicorn  # noqa: E402 — must run after the event loop policy

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        loop="none",  # Windows + psycopg async (see module docstring)
    )
