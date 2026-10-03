"""Delivery platform presence per restaurant.

Compliance: presence is NEVER detected by scraping delivery platforms
(their ToS forbid it) — only via the restaurant's own public website
(`website_link`) or manual confirmation by sales (`manual`).
The method is recorded in `detection_method`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DeliveryPlatform, DetectionMethod, pg_enum


class DeliveryPresence(Base):
    __tablename__ = "delivery_presence"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[DeliveryPlatform] = mapped_column(
        pg_enum(DeliveryPlatform, "delivery_platform"), nullable=False
    )
    detected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)  # link found on the restaurant's site

    detection_method: Mapped[DetectionMethod] = mapped_column(
        pg_enum(DetectionMethod, "detection_method"), nullable=False
    )

    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurant: Mapped["Restaurant"] = relationship(  # noqa: F821
        back_populates="delivery_presence"
    )
