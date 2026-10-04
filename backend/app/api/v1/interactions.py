"""Interactions: the append-only commercial history (docs/API.md).

There is deliberately no PUT/PATCH/DELETE — history is immutable.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import Interaction, User
from app.schemas.common import MAX_PAGE_SIZE, Page
from app.schemas.crm import InteractionCreate, InteractionCreated
from app.schemas.restaurant import FollowUpOut, InteractionOut
from app.services import interaction_service, restaurant_service

router = APIRouter()


@router.get("/restaurants/{restaurant_id}/interactions", response_model=Page[InteractionOut])
async def list_interactions(
    restaurant_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> Page[InteractionOut]:
    restaurant = await restaurant_service.get_restaurant(db, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante no encontrado")

    base = select(Interaction).where(Interaction.restaurant_id == restaurant_id)
    total = (await db.scalars(select(func.count()).select_from(base.subquery()))).one()
    stmt = (
        base.order_by(Interaction.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    interactions = (await db.scalars(stmt)).all()
    return Page(
        items=[InteractionOut.model_validate(i) for i in interactions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/restaurants/{restaurant_id}/interactions",
    response_model=InteractionCreated,
    status_code=status.HTTP_201_CREATED,
)
async def register_interaction(
    restaurant_id: UUID,
    payload: InteractionCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> InteractionCreated:
    """Record a contact attempt: syncs the lead status and may schedule
    a follow-up automatically (no_answer -> +3 days by default)."""
    result = await interaction_service.register_interaction(
        db, restaurant_id, payload, user
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante no encontrado")
    await db.commit()

    await db.refresh(result.interaction)
    if result.follow_up is not None:
        await db.refresh(result.follow_up)
    return InteractionCreated(
        interaction=InteractionOut.model_validate(result.interaction),
        lead_status=result.lead.status,
        follow_up_created=(
            FollowUpOut.model_validate(result.follow_up)
            if result.follow_up is not None
            else None
        ),
    )
