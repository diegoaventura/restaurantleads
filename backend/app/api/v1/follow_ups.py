"""Follow-ups: the daily agenda of pending callbacks (docs/API.md).

Paths are explicit (no prefix): the global agenda at /follow-ups plus
the per-restaurant nested routes.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import FollowUp, User
from app.models.enums import FollowUpStatus
from app.schemas.common import MAX_PAGE_SIZE, Page
from app.schemas.crm import FollowUpActionRequest, FollowUpCreate, FollowUpItem
from app.schemas.restaurant import FollowUpOut
from app.services import follow_up_service, restaurant_service

router = APIRouter()


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def _list(
    db: AsyncSession,
    *,
    restaurant_id: UUID | None = None,
    follow_up_status: FollowUpStatus | None = None,
    due_on: date | None = None,
    due_before: date | None = None,
    page: int,
    page_size: int,
) -> Page[FollowUpItem]:
    base = select(FollowUp)
    if restaurant_id is not None:
        base = base.where(FollowUp.restaurant_id == restaurant_id)
    if follow_up_status is not None:
        base = base.where(FollowUp.status == follow_up_status)
    if due_on is not None:
        start, end = _day_bounds(due_on)
        base = base.where(FollowUp.scheduled_at >= start, FollowUp.scheduled_at < end)
    if due_before is not None:
        _start, end = _day_bounds(due_before)
        base = base.where(FollowUp.scheduled_at < end)

    total = (await db.scalars(select(func.count()).select_from(base.subquery()))).one()
    stmt = (
        base.order_by(FollowUp.scheduled_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    follow_ups = (await db.scalars(stmt)).all()

    # Restaurant names for the agenda (one query per page item, fine here).
    items: list[FollowUpItem] = []
    for follow_up in follow_ups:
        restaurant = await restaurant_service.get_restaurant(db, follow_up.restaurant_id)
        items.append(
            FollowUpItem(
                **FollowUpOut.model_validate(follow_up).model_dump(),
                restaurant_id=follow_up.restaurant_id,
                restaurant_name=restaurant.name if restaurant else "?",
            )
        )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/follow-ups", response_model=Page[FollowUpItem])
async def list_follow_ups(
    follow_up_status: FollowUpStatus | None = Query(None, alias="status"),
    due_on: date | None = None,
    due_before: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> Page[FollowUpItem]:
    return await _list(
        db,
        follow_up_status=follow_up_status,
        due_on=due_on,
        due_before=due_before,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/restaurants/{restaurant_id}/follow-ups", response_model=Page[FollowUpItem]
)
async def list_restaurant_follow_ups(
    restaurant_id: UUID,
    follow_up_status: FollowUpStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> Page[FollowUpItem]:
    restaurant = await restaurant_service.get_restaurant(db, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante no encontrado")
    return await _list(
        db,
        restaurant_id=restaurant_id,
        follow_up_status=follow_up_status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/restaurants/{restaurant_id}/follow-ups",
    response_model=FollowUpOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_follow_up(
    restaurant_id: UUID,
    payload: FollowUpCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> FollowUpOut:
    restaurant = await restaurant_service.get_restaurant(db, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante no encontrado")
    follow_up = await follow_up_service.create_follow_up(
        db, restaurant_id, payload, created_by=user.id
    )
    await db.commit()
    await db.refresh(follow_up)
    return FollowUpOut.model_validate(follow_up)


@router.patch("/follow-ups/{follow_up_id}", response_model=FollowUpOut)
async def act_on_follow_up(
    follow_up_id: UUID,
    payload: FollowUpActionRequest,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> FollowUpOut:
    follow_up = await follow_up_service.get_follow_up(db, follow_up_id)
    if follow_up is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Seguimiento no encontrado")
    try:
        follow_up = await follow_up_service.apply_action(
            follow_up,
            action=payload.action,
            new_date=payload.new_date,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
        ) from exc
    await db.commit()
    await db.refresh(follow_up)
    return FollowUpOut.model_validate(follow_up)


# NOTE: there is deliberately no DELETE route — follow-ups are completed
# or cancelled (audit trail), never deleted. An undefined method returns
# 405 from the framework itself.
