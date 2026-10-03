"""Health check (public)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger("app")


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db_session)) -> dict:
    settings = get_settings()
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 — liveness must never crash
        logger.exception("Health check: database unreachable")
        database = "error"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "version": settings.app_version,
        "database": database,
    }
