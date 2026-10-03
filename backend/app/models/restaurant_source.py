"""Provenance of every restaurant (traceability, GDPR record keeping).

One row per restaurant+source; the same restaurant appearing in two
sources adds rows, never a duplicate restaurant.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SourceType, pg_enum


class RestaurantSource(Base):
    __tablename__ = "restaurant_sources"
    __table_args__ = (
        # NULLS NOT DISTINCT (PG15+): one row per restaurant+source even
        # when external_id is NULL (manual entries without external id).
        UniqueConstraint(
            "restaurant_id",
            "source",
            "external_id",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_restaurant_sources_source_external_id", "source", "external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[SourceType] = mapped_column(
        pg_enum(SourceType, "source_type"), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)  # e.g. OSM "node/123"

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurant: Mapped["Restaurant"] = relationship(  # noqa: F821
        back_populates="sources"
    )
