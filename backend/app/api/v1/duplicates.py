"""Duplicate review queue (plan FASE 4: no auto-merge of uncertain matches)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import Restaurant
from app.schemas.common import MAX_PAGE_SIZE, Message, Page
from app.schemas.duplicates import DuplicateItem, ResolveRequest
from app.schemas.restaurant import RestaurantOut
from app.services import dedup
from app.services.restaurant_service import DUPLICATE_QUEUE_OPTIONS

router = APIRouter()


@router.get("", response_model=Page[DuplicateItem])
async def list_duplicates(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db_session),
    _user=Depends(get_current_user),
) -> Page[DuplicateItem]:
    stmt = select(Restaurant).where(
        Restaurant.deleted_at.is_(None),
        Restaurant.possible_duplicate_of_id.is_not(None),
    )
    total = (await db.scalars(select(func.count()).select_from(stmt.subquery()))).one()
    stmt = stmt.options(*DUPLICATE_QUEUE_OPTIONS).offset((page - 1) * page_size).limit(page_size)
    suspects = (await db.scalars(stmt)).all()

    items = [
        DuplicateItem(
            restaurant=RestaurantOut.model_validate(suspect),
            duplicate_of=RestaurantOut.model_validate(suspect.possible_duplicate_of),
        )
        for suspect in suspects
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/{restaurant_id}/resolve", response_model=Message)
async def resolve_duplicate(
    restaurant_id: UUID,
    payload: ResolveRequest,
    db: AsyncSession = Depends(get_db_session),
    _user=Depends(get_current_user),
) -> Message:
    stmt = (
        select(Restaurant)
        .where(
            Restaurant.id == restaurant_id,
            Restaurant.deleted_at.is_(None),
            Restaurant.possible_duplicate_of_id.is_not(None),
        )
        .options(*DUPLICATE_QUEUE_OPTIONS)
    )
    suspect = (await db.scalars(stmt)).first()
    if suspect is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Duplicado no encontrado (¿ya está resuelto?)",
        )

    try:
        await dedup.resolve_duplicate(db, suspect, action=payload.action)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await db.commit()

    action_text = "fusionado con el original" if payload.action == "merge" else "marcado como no duplicado"
    return Message(detail=f"Duplicado {action_text}")
