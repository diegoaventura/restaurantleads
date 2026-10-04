"""Interaction registration: append-only history + lead status sync.

Interactions are NEVER updated or deleted (docs/DATABASE.md). Registering
one syncs the lead status automatically from the result, bridging through
CONTACTED when the state machine needs it (a new interaction means the
business was reached again).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utcnow
from app.models import FollowUp, Interaction, Lead, Restaurant, User
from app.models.enums import InteractionResult, LeadStatus
from app.schemas.crm import InteractionCreate
from app.services import follow_up_service, lead_service

logger = logging.getLogger("app")

# Result -> the lead status it implies.
INTERACTION_STATUS_MAP: dict[InteractionResult, LeadStatus] = {
    InteractionResult.NO_ANSWER: LeadStatus.NO_RESPONSE,
    InteractionResult.BUSY: LeadStatus.NO_RESPONSE,
    InteractionResult.CALLBACK_REQUESTED: LeadStatus.NO_RESPONSE,
    InteractionResult.INTERESTED: LeadStatus.INTERESTED,
    InteractionResult.NOT_INTERESTED: LeadStatus.NOT_INTERESTED,
    InteractionResult.WRONG_NUMBER: LeadStatus.WRONG_NUMBER,
    InteractionResult.OUT_OF_AREA: LeadStatus.OUT_OF_AREA,
    InteractionResult.MEETING_SCHEDULED: LeadStatus.MEETING,
    InteractionResult.DUPLICATE_REPORTED: LeadStatus.DUPLICATE,
}

# Statuses from which a new interaction bridges through CONTACTED.
_BRIDGE_STATUSES = {
    LeadStatus.NEW,
    LeadStatus.QUALIFIED,
    LeadStatus.NO_RESPONSE,
    LeadStatus.FOLLOW_UP,
}


@dataclass
class RegisteredInteraction:
    interaction: Interaction
    lead: Lead
    follow_up: FollowUp | None


async def register_interaction(
    db: AsyncSession,
    restaurant_id: UUID,
    payload: InteractionCreate,
    user: User,
) -> RegisteredInteraction | None:
    """Create the interaction, sync the lead, maybe auto follow-up.

    Does NOT commit — the caller owns the transaction. Returns None when
    the restaurant does not exist.
    """
    stmt = (
        select(Restaurant)
        .where(Restaurant.id == restaurant_id, Restaurant.deleted_at.is_(None))
        .options(selectinload(Restaurant.lead))
    )
    restaurant = (await db.scalars(stmt)).first()
    if restaurant is None:
        return None

    interaction = Interaction(
        restaurant_id=restaurant.id,
        channel=payload.channel,
        occurred_at=payload.occurred_at or utcnow(),
        result=payload.result,
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(interaction)

    lead = restaurant.lead
    if lead is None:
        lead = Lead()
        restaurant.lead = lead
    _sync_lead_status(lead, payload.result, is_admin=user.role.value == "admin")

    follow_up = await follow_up_service.create_auto_follow_up(
        db, interaction, created_by=user.id
    )
    return RegisteredInteraction(interaction=interaction, lead=lead, follow_up=follow_up)


def _sync_lead_status(lead: Lead, result: InteractionResult, *, is_admin: bool) -> None:
    """Move the lead to the status implied by the interaction result.

    Strict: only table transitions (with a bridge through CONTACTED when
    the current status allows it). If nothing valid applies, the status
    stays untouched — the interaction log is the source of truth.
    """
    target = INTERACTION_STATUS_MAP.get(result)
    if target is None or target == lead.status:
        return
    try:
        lead_service.validate_transition(lead.status, target, is_admin=is_admin)
    except lead_service.InvalidTransition:
        if lead.status not in _BRIDGE_STATUSES:
            logger.warning(
                "Status sync skipped: %s -> %s not allowed (lead stays %s)",
                lead.status.value, target.value, lead.status.value,
            )
            return
        try:  # bridge: we reached them again -> CONTACTED -> target
            lead_service.validate_transition(
                lead.status, LeadStatus.CONTACTED, is_admin=is_admin
            )
            lead_service.validate_transition(
                LeadStatus.CONTACTED, target, is_admin=is_admin
            )
        except lead_service.InvalidTransition:
            logger.warning(
                "Status sync skipped (bridge failed): %s -> %s",
                lead.status.value, target.value,
            )
            return
    lead.status = target
