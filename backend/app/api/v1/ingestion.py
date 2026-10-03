"""Ingestion endpoints (admin only).

`POST /run` executes a connector through the pipeline; `dry_run` runs
everything and rolls back, so counts are real without writing anything.
Run history (persisting each run) is deferred — noted in docs/ROADMAP.md.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_admin
from app.ingestion import pipeline
from app.ingestion.base import IngestionError
from app.ingestion.registry import CONNECTOR_METADATA, build_connector
from app.ingestion.registry import UnknownConnectorError
from app.models import User
from app.schemas.ingestion import IngestionRunRequest, IngestionRunResult

router = APIRouter()
logger = logging.getLogger("app")


@router.get("/connectors")
async def list_connectors(
    _admin: User = Depends(require_admin),
) -> list[dict]:
    return CONNECTOR_METADATA


@router.post("/run", response_model=IngestionRunResult)
async def run_ingestion(
    payload: IngestionRunRequest,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_admin),
) -> IngestionRunResult:
    try:
        connector = build_connector(payload.connector, payload.params)
    except UnknownConnectorError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except IngestionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    logger.info("Ingestion run start: connector=%s dry_run=%s", payload.connector, payload.dry_run)
    try:
        result = await pipeline.run_ingestion(db, connector, dry_run=payload.dry_run)
    except IngestionError as exc:
        await db.rollback()
        logger.warning("Ingestion run failed: connector=%s error=%s", payload.connector, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Error de ingesta: {exc}"
        ) from exc
    logger.info(
        "Ingestion run done: connector=%s received=%s new=%s exact=%s possible=%s invalid=%s",
        result.connector, result.received, result.new,
        result.exact_duplicates, result.possible_duplicates, result.invalid,
    )
    return result
