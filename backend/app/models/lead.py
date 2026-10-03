"""Commercial lead state. One-to-one with restaurants.

`score` (0-100) is computed by the scoring service from configurable rules
(M4) and always stored together with `score_reasons` — a score is never
a black box number.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import LeadPriority, LeadStatus, pg_enum


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
        Index("ix_leads_score", text("score DESC")),
        Index("ix_leads_status_updated_at", "status", text("updated_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("restaurants.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    score: Mapped[int | None] = mapped_column(SmallInteger)  # 0..100, null until first scoring
    score_reasons: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB
    )  # [{factor, points}]
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[LeadStatus] = mapped_column(
        pg_enum(LeadStatus, "lead_status"),
        default=LeadStatus.NEW,
        nullable=False,
        index=True,
    )
    priority: Mapped[LeadPriority] = mapped_column(
        pg_enum(LeadPriority, "lead_priority"),
        default=LeadPriority.MEDIUM,
        nullable=False,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    restaurant: Mapped["Restaurant"] = relationship(  # noqa: F821
        back_populates="lead"
    )
