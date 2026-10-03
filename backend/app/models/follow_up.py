"""Scheduled follow-ups.

Created manually by sales or automatically by the CRM service when an
interaction ends with `no_answer` (+3 days, configurable in M4/M5).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FollowUpStatus, InteractionChannel, pg_enum


class FollowUp(Base):
    __tablename__ = "follow_ups"
    __table_args__ = (
        # Feeds "follow-ups due today" (dashboard).
        Index("ix_follow_ups_status_scheduled_at", "status", "scheduled_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    channel: Mapped[InteractionChannel] = mapped_column(
        pg_enum(InteractionChannel, "interaction_channel"), nullable=False
    )
    status: Mapped[FollowUpStatus] = mapped_column(
        pg_enum(FollowUpStatus, "follow_up_status"),
        default=FollowUpStatus.PENDING,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurant: Mapped["Restaurant"] = relationship(  # noqa: F821
        back_populates="follow_ups"
    )
