"""Restaurant queries: filtered/paginated listing and fetching.

Query building lives here (not in the router) so later milestones reuse
the same filters. Soft-deleted restaurants are always excluded.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    DeliveryPresence,
    Lead,
    Restaurant,
    RestaurantSource,
)
from app.models.enums import DeliveryPlatform, LeadStatus, SourceType

# Eager loading: the list needs the lead summary; the detail everything.
LIST_OPTIONS = (selectinload(Restaurant.lead),)
DETAIL_OPTIONS = (
    selectinload(Restaurant.lead),
    selectinload(Restaurant.sources),
    selectinload(Restaurant.delivery_presence),
    selectinload(Restaurant.contacts),
    selectinload(Restaurant.interactions),
    selectinload(Restaurant.follow_ups),
)

SORTABLE_COLUMNS = {"score", "name", "updated_at"}


async def list_restaurants(
    db: AsyncSession,
    *,
    search: str | None = None,
    city: str | None = None,
    category: str | None = None,
    status: LeadStatus | None = None,
    platform: DeliveryPlatform | None = None,
    source: SourceType | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    has_phone: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort: str = "updated_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Restaurant], int]:
    """Return (restaurants, total) matching the filters."""
    stmt = select(Restaurant).where(Restaurant.deleted_at.is_(None))

    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Restaurant.name.ilike(pattern),
                Restaurant.phone.ilike(pattern),
                Restaurant.normalized_name.ilike(pattern),
            )
        )
    if city:
        stmt = stmt.where(Restaurant.city.ilike(city.strip()))
    if category:
        stmt = stmt.where(Restaurant.category.ilike(category.strip()))
    if has_phone is True:
        stmt = stmt.where(Restaurant.phone.is_not(None))
    if created_from is not None:
        stmt = stmt.where(Restaurant.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(Restaurant.created_at <= created_to)

    needs_lead_join = (
        status is not None
        or min_score is not None
        or max_score is not None
        or sort == "score"
    )
    if needs_lead_join:
        stmt = stmt.outerjoin(Restaurant.lead)
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if min_score is not None:
            stmt = stmt.where(Lead.score >= min_score)
        if max_score is not None:
            stmt = stmt.where(Lead.score <= max_score)

    if platform is not None:
        stmt = stmt.where(
            exists().where(
                DeliveryPresence.restaurant_id == Restaurant.id,
                DeliveryPresence.platform == platform,
            )
        )
    if source is not None:
        stmt = stmt.where(
            exists().where(
                RestaurantSource.restaurant_id == Restaurant.id,
                RestaurantSource.source == source,
            )
        )

    # Count before options/order/limit (kept out of the subquery).
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.scalars(count_stmt)).one()

    # Sorting (whitelisted by the router's Query pattern).
    if sort == "score":
        column = Lead.score
    elif sort == "name":
        column = Restaurant.normalized_name
    else:
        column = Restaurant.updated_at
    direction = column.desc() if order == "desc" else column.asc()
    if sort == "score":
        direction = direction.nulls_last()  # unscored leads go last
    stmt = stmt.order_by(direction).options(*LIST_OPTIONS)

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    restaurants = list((await db.scalars(stmt)).all())
    return restaurants, total


async def get_restaurant(
    db: AsyncSession, restaurant_id: UUID, *, detail: bool = False
) -> Restaurant | None:
    """Fetch a non-deleted restaurant with relations; None if missing."""
    options = DETAIL_OPTIONS if detail else LIST_OPTIONS
    stmt = (
        select(Restaurant)
        .where(Restaurant.id == restaurant_id, Restaurant.deleted_at.is_(None))
        .options(*options)
    )
    return (await db.scalars(stmt)).first()
