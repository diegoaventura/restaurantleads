"""CRM schemas: interactions (append-only) and follow-ups."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import (
    FollowUpStatus,
    InteractionChannel,
    InteractionResult,
    LeadStatus,
)
from app.schemas.restaurant import FollowUpOut, InteractionOut


class InteractionCreate(BaseModel):
    channel: InteractionChannel
    result: InteractionResult
    occurred_at: datetime | None = None  # defaults to now (UTC)
    notes: str | None = None


class InteractionCreated(BaseModel):
    interaction: InteractionOut
    lead_status: LeadStatus  # the status automatically synced
    follow_up_created: FollowUpOut | None


class FollowUpCreate(BaseModel):
    scheduled_at: datetime
    channel: InteractionChannel
    notes: str | None = None


class FollowUpActionRequest(BaseModel):
    action: Literal["complete", "postpone", "cancel"]
    new_date: datetime | None = None  # required for postpone
    notes: str | None = None


class FollowUpStatusFilter(BaseModel):
    status: FollowUpStatus | None = None
    due_on: date | None = None
    due_before: date | None = None


class FollowUpItem(FollowUpOut):
    """Follow-up plus the restaurant it belongs to (for the daily agenda)."""

    restaurant_id: UUID
    restaurant_name: str
