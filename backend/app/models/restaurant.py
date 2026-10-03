"""Restaurants: the core entity of the system.

Every enriched contact field records its source and last verification
timestamp — enrichment never silently overwrites data (docs/DATABASE.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import SourceType, pg_enum


class Restaurant(TimestampMixin, Base):
    __tablename__ = "restaurants"
    __table_args__ = (
        Index("ix_restaurants_city_category", "city", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # --- Contact data, each with source + last verification ---
    phone: Mapped[str | None] = mapped_column(Text, index=True)  # E.164, e.g. +34612345678
    phone_source: Mapped[SourceType | None] = mapped_column(pg_enum(SourceType, "source_type"))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    email: Mapped[str | None] = mapped_column(Text)
    email_source: Mapped[SourceType | None] = mapped_column(pg_enum(SourceType, "source_type"))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    website: Mapped[str | None] = mapped_column(Text)  # normalized root domain
    website_source: Mapped[SourceType | None] = mapped_column(pg_enum(SourceType, "source_type"))
    website_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Location ---
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text, index=True)
    postal_code: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))

    category: Mapped[str | None] = mapped_column(Text)  # e.g. "kebab", "pizzeria"

    # --- Deduplication & GDPR ---
    # Never auto-merged: uncertain matches only mark this field for review.
    possible_duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("restaurants.id", ondelete="SET NULL")
    )
    possible_duplicate_of: Mapped["Restaurant | None"] = relationship(
        remote_side=[id], lazy="selectin"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # soft delete

    # --- Relationships (read side) ---
    sources: Mapped[list["RestaurantSource"]] = relationship(  # noqa: F821
        back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )
    delivery_presence: Mapped[list["DeliveryPresence"]] = relationship(  # noqa: F821
        back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )
    interactions: Mapped[list["Interaction"]] = relationship(  # noqa: F821
        back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )
    lead: Mapped["Lead | None"] = relationship(  # noqa: F821
        back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )
    follow_ups: Mapped[list["FollowUp"]] = relationship(  # noqa: F821
        back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )
    ai_generations: Mapped[list["AIGeneration"]] = relationship(  # noqa: F821
        back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )
