"""Follow-ups: creation, automatic scheduling from interaction results, actions.

`no_answer`/`busy` -> +FOLLOW_UP_DELAY_DAYS (default 3, the plan's example:
call 03/10 -> follow-up 06/10). `callback_requested` -> +1 day.
Postponing keeps the follow-up PENDING (it must still appear on the new
date in the agenda).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import utcnow
from app.models import FollowUp, Interaction
from app.models.enums import FollowUpStatus, InteractionResult
from app.schemas.crm import FollowUpCreate

logger = logging.getLogger("app")


def auto_follow_up_delay(result: InteractionResult) -> int | None:
    """Days until the automatic follow-up, or None if the result needs none."""
    settings = get_settings()
    if result in (InteractionResult.NO_ANSWER, InteractionResult.BUSY):
        return settings.follow_up_delay_days
    if result == InteractionResult.CALLBACK_REQUESTED:
        return settings.follow_up_callback_delay_days
    return None


async def create_auto_follow_up(
    db: AsyncSession, interaction: Interaction, *, created_by: UUID | None
) -> FollowUp | None:
    """Schedule the follow-up implied by an interaction result, if any."""
    delay_days = auto_follow_up_delay(interaction.result)
    if delay_days is None:
        return None
    follow_up = FollowUp(
        restaurant_id=interaction.restaurant_id,
        scheduled_at=interaction.occurred_at + timedelta(days=delay_days),
        channel=interaction.channel,
        notes=f"Automático tras resultado '{interaction.result.value}'",
        created_by=created_by,
    )
    db.add(follow_up)
    return follow_up


async def create_follow_up(
    db: AsyncSession,
    restaurant_id: UUID,
    payload: FollowUpCreate,
    *,
    created_by: UUID | None,
) -> FollowUp:
    follow_up = FollowUp(
        restaurant_id=restaurant_id,
        scheduled_at=payload.scheduled_at,
        channel=payload.channel,
        notes=payload.notes,
        created_by=created_by,
    )
    db.add(follow_up)
    return follow_up


async def apply_action(
    follow_up: FollowUp,
    *,
    action: str,
    new_date=None,
    notes: str | None = None,
) -> FollowUp:
    """Complete/postpone/cancel a PENDING follow-up (the agenda's actions)."""
    if follow_up.status != FollowUpStatus.PENDING:
        raise ValueError(
            f"No se puede actuar sobre un seguimiento '{follow_up.status.value}'"
        )
    if notes:
        follow_up.notes = (
            f"{follow_up.notes}\n{notes}" if follow_up.notes else notes
        )

    if action == "complete":
        follow_up.status = FollowUpStatus.COMPLETED
        follow_up.completed_at = utcnow()
    elif action == "postpone":
        if new_date is None:
            raise ValueError("postpone requiere new_date")
        follow_up.scheduled_at = new_date  # stays PENDING for the new date
    elif action == "cancel":
        follow_up.status = FollowUpStatus.CANCELLED
    else:  # pragma: no cover — schema Literal already restricts this
        raise ValueError(f"Acción no soportada: {action}")
    return follow_up


async def get_follow_up(db: AsyncSession, follow_up_id: UUID) -> FollowUp | None:
    stmt = select(FollowUp).where(FollowUp.id == follow_up_id)
    return (await db.scalars(stmt)).first()
