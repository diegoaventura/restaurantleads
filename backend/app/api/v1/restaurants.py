"""Restaurants and leads (the main operational resource).

Lead is 1:1 with the restaurant and is managed nested (docs/API.md).
Interactions and follow-ups endpoints arrive in M5; scoring in M4.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.db.base import utcnow
from app.models import Lead, Restaurant, RestaurantSource, User
from app.models.enums import (
    DeliveryPlatform,
    LeadStatus,
    SourceType,
)
from app.schemas.common import MAX_PAGE_SIZE, Message, Page
from app.schemas.restaurant import (
    LeadOut,
    LeadUpdate,
    RestaurantCreate,
    RestaurantDetail,
    RestaurantOut,
    RestaurantUpdate,
)
from app.services import lead_service, restaurant_service
from app.services.normalization import normalize_name

router = APIRouter()


async def _get_or_404(
    db: AsyncSession, restaurant_id: UUID, *, detail: bool = False
) -> Restaurant:
    restaurant = await restaurant_service.get_restaurant(
        db, restaurant_id, detail=detail
    )
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante no encontrado")
    return restaurant


@router.get("", response_model=Page[RestaurantOut])
async def list_restaurants(
    search: str | None = None,
    city: str | None = None,
    category: str | None = None,
    lead_status: LeadStatus | None = Query(None, alias="status"),
    platform: DeliveryPlatform | None = None,
    source: SourceType | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    max_score: int | None = Query(None, ge=0, le=100),
    has_phone: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort: str = Query("updated_at", pattern="^(score|name|updated_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> Page[RestaurantOut]:
    restaurants, total = await restaurant_service.list_restaurants(
        db,
        search=search,
        city=city,
        category=category,
        status=lead_status,
        platform=platform,
        source=source,
        min_score=min_score,
        max_score=max_score,
        has_phone=has_phone,
        created_from=created_from,
        created_to=created_to,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[RestaurantOut.model_validate(r) for r in restaurants],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=RestaurantDetail, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    payload: RestaurantCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Restaurant:
    """Manual creation: registers provenance and opens the lead (NEW)."""
    now = utcnow()
    data = payload.model_dump()
    contact_fields = {"phone": SourceType.MANUAL, "email": SourceType.MANUAL, "website": SourceType.MANUAL}
    kwargs: dict = {}
    for field, source in contact_fields.items():
        if data.get(field):
            kwargs[f"{field}_source"] = source
            kwargs[f"{field}_verified_at"] = now

    restaurant = Restaurant(
        **data,
        **kwargs,
        normalized_name=normalize_name(payload.name),
    )
    restaurant.sources = [RestaurantSource(source=SourceType.MANUAL)]
    restaurant.lead = Lead(assigned_to=user.id)
    db.add(restaurant)
    await db.commit()

    return await _get_or_404(db, restaurant.id, detail=True)


@router.get("/{restaurant_id}", response_model=RestaurantDetail)
async def get_restaurant(
    restaurant_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> Restaurant:
    return await _get_or_404(db, restaurant_id, detail=True)


@router.patch("/{restaurant_id}", response_model=RestaurantDetail)
async def update_restaurant(
    restaurant_id: UUID,
    payload: RestaurantUpdate,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> Restaurant:
    """Rectification (GDPR): edited contact fields get MANUAL source + timestamp."""
    restaurant = await _get_or_404(db, restaurant_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"]:
        restaurant.normalized_name = normalize_name(data["name"])
    for field in ("phone", "email", "website"):
        if field in data and data[field]:
            setattr(restaurant, f"{field}_source", SourceType.MANUAL)
            setattr(restaurant, f"{field}_verified_at", utcnow())
    for field, value in data.items():
        setattr(restaurant, field, value)

    await db.commit()
    return await _get_or_404(db, restaurant_id, detail=True)


@router.delete("/{restaurant_id}", response_model=Message)
async def soft_delete_restaurant(
    restaurant_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> Message:
    """Soft delete (GDPR erasure access); hard delete is admin-only (later)."""
    restaurant = await _get_or_404(db, restaurant_id)
    restaurant.deleted_at = utcnow()
    await db.commit()
    return Message(detail="Restaurante eliminado (soft delete)")


@router.patch("/{restaurant_id}/lead", response_model=LeadOut)
async def update_lead(
    restaurant_id: UUID,
    payload: LeadUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Lead:
    from app.models.enums import UserRole

    restaurant = await _get_or_404(db, restaurant_id, detail=False)
    lead = restaurant.lead
    if lead is None:  # restaurants created outside the API (seed/ingestion)
        lead = Lead(restaurant=restaurant, assigned_to=user.id)
        restaurant.lead = lead

    data = payload.model_dump(exclude_unset=True)

    if "assigned_to" in data and data["assigned_to"] is not None:
        assignee = await db.get(User, data["assigned_to"])
        if assignee is None or not assignee.is_active:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Usuario asignado no encontrado o inactivo"
            )
        lead.assigned_to = assignee.id

    if data.get("priority") is not None:
        lead.priority = data["priority"]

    if data.get("status") is not None and data["status"] != lead.status:
        try:
            lead_service.validate_transition(
                lead.status, data["status"], is_admin=user.role == UserRole.ADMIN
            )
        except lead_service.InvalidTransition as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
            ) from exc
        lead.status = data["status"]

    await db.commit()
    await db.refresh(lead)
    return lead
