"""AI-generated content (briefings, call scripts, messages).

Content is ALWAYS reviewed by a human before any commercial use — there is
no send endpoint. Provenance is kept: prompt version, provider and model.
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
from app.models.enums import GenerationType, pg_enum


class AIGeneration(Base):
    __tablename__ = "ai_generations"
    __table_args__ = (
        Index("ix_ai_generations_restaurant_created_at", "restaurant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False
    )
    generation_type: Mapped[GenerationType] = mapped_column(
        pg_enum(GenerationType, "generation_type"), nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. "call_script_v1"
    provider: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. "groq", "mock"
    model: Mapped[str] = mapped_column(Text, nullable=False)
    generated_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurant: Mapped["Restaurant"] = relationship(  # noqa: F821
        back_populates="ai_generations"
    )
