"""Duplicate detection and resolution (plan FASE 4, docs/DATABASE.md).

Matching priority:
1. external_id + source            → EXACT
2. phone (E.164)                   → EXACT
3. website root domain             → EXACT
4. normalized name + address       → EXACT
5. name similarity + proximity    → POSSIBLE (human review, never auto-merged)

Nothing is ever deleted automatically: uncertain matches only mark
`possible_duplicate_of` and wait in the review queue (/duplicates).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models import (
    DeliveryPresence,
    Restaurant,
    RestaurantSource,
)
from app.models.enums import SourceType
from app.schemas.ingestion import RestaurantCandidate
from app.services.normalization import (
    normalize_name,
    normalize_phone,
    normalize_website,
)
from app.services.restaurant_service import DUPLICATE_QUEUE_OPTIONS

NAME_SIMILARITY_THRESHOLD = 85  # token_sort_ratio, normalized names
PROXIMITY_METERS = 300
SCAN_LIMIT = 2000  # cap for the similarity scan


class MatchType(str, enum.Enum):
    NONE = "none"
    EXACT = "exact"
    POSSIBLE = "possible"


@dataclass
class Match:
    type: MatchType
    criterion: str = ""
    restaurant: Restaurant | None = None


def _distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Haversine distance in meters."""
    radius = 6_371_000.0
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = (
        sin(d_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    )
    return 2 * radius * asin(sqrt(a))


async def find_source_row(
    db: AsyncSession,
    restaurant_id: UUID,
    source: SourceType,
    external_id: str | None,
) -> RestaurantSource | None:
    """Find a provenance row; NULL external_id compares as NULL (PG)."""
    stmt = select(RestaurantSource).where(
        RestaurantSource.restaurant_id == restaurant_id,
        RestaurantSource.source == source,
        RestaurantSource.external_id.is_(None)
        if external_id is None
        else RestaurantSource.external_id == external_id,
    )
    return (await db.scalars(stmt)).first()


async def find_match(
    db: AsyncSession, candidate: RestaurantCandidate
) -> Match:
    not_deleted = Restaurant.deleted_at.is_(None)
    # Normalize defensively so find_match is correct regardless of the caller.
    phone = normalize_phone(candidate.phone)
    website = normalize_website(candidate.website)

    # 1) external_id + source
    if candidate.external_id and candidate.source:
        stmt = (
            select(Restaurant)
            .join(RestaurantSource)
            .where(
                not_deleted,
                RestaurantSource.source == candidate.source,
                RestaurantSource.external_id == candidate.external_id,
            )
        )
        restaurant = (await db.scalars(stmt)).first()
        if restaurant is not None:
            return Match(MatchType.EXACT, "external_id", restaurant)

    # 2) phone (E.164)
    if phone:
        stmt = select(Restaurant).where(not_deleted, Restaurant.phone == phone)
        restaurant = (await db.scalars(stmt)).first()
        if restaurant is not None:
            return Match(MatchType.EXACT, "phone", restaurant)

    # 3) website root domain
    if website:
        stmt = select(Restaurant).where(not_deleted, Restaurant.website == website)
        restaurant = (await db.scalars(stmt)).first()
        if restaurant is not None:
            return Match(MatchType.EXACT, "website", restaurant)

    # 4) normalized name + address
    if candidate.name and candidate.address:
        normalized_address = normalize_name(candidate.address)
        stmt = select(Restaurant).where(
            not_deleted,
            Restaurant.normalized_name == normalize_name(candidate.name),
        )
        for restaurant in (await db.scalars(stmt)).all():
            if (
                restaurant.address
                and normalize_name(restaurant.address) == normalized_address
            ):
                return Match(MatchType.EXACT, "name_address", restaurant)

    # 5) name similarity + geographic proximity (within the same city)
    #    Requires coordinates on both sides — without them we stay
    #    conservative (a repeated name may be a different franchise).
    if (
        candidate.name
        and candidate.city
        and candidate.latitude is not None
        and candidate.longitude is not None
    ):
        normalized_name = normalize_name(candidate.name)
        stmt = (
            select(Restaurant)
            .where(
                not_deleted,
                Restaurant.city.ilike(candidate.city.strip()),
                Restaurant.latitude.is_not(None),
                Restaurant.longitude.is_not(None),
            )
            .limit(SCAN_LIMIT)
        )
        best: Restaurant | None = None
        best_score = 0
        for restaurant in (await db.scalars(stmt)).all():
            score = fuzz.token_sort_ratio(
                normalized_name, restaurant.normalized_name
            )
            if score < NAME_SIMILARITY_THRESHOLD:
                continue
            distance = _distance_meters(
                candidate.latitude,
                candidate.longitude,
                float(restaurant.latitude),  # type: ignore[arg-type]
                float(restaurant.longitude),  # type: ignore[arg-type]
            )
            if distance <= PROXIMITY_METERS and score > best_score:
                best, best_score = restaurant, score
        if best is not None:
            return Match(MatchType.POSSIBLE, "similarity_proximity", best)

    return Match(MatchType.NONE)


async def resolve_duplicate(
    db: AsyncSession, suspect: Restaurant, *, action: str
) -> None:
    """Resolve a review-queue item. `merge` is user-confirmed, never auto."""
    # Re-fetch with all collections loaded: lazy loads are impossible in
    # async sessions, and callers may pass a freshly marked suspect.
    stmt = (
        select(Restaurant)
        .where(Restaurant.id == suspect.id)
        .options(*DUPLICATE_QUEUE_OPTIONS)
    )
    loaded = (await db.scalars(stmt)).unique().one()
    suspect = loaded

    original = await db.get(Restaurant, suspect.possible_duplicate_of_id)
    if original is None:
        raise ValueError("Restaurante original no encontrado")

    if action == "keep_both":
        suspect.possible_duplicate_of_id = None
        return

    if action != "merge":
        raise ValueError(f"Acción no soportada: {action}")

    # Fill missing fields on the original — never overwrite existing data.
    for field in (
        "address",
        "city",
        "postal_code",
        "latitude",
        "longitude",
        "category",
    ):
        suspect_value = getattr(suspect, field)
        if getattr(original, field) is None and suspect_value is not None:
            setattr(original, field, suspect_value)
    for field in ("phone", "email", "website"):
        suspect_value = getattr(suspect, field)
        if getattr(original, field) is None and suspect_value is not None:
            setattr(original, field, suspect_value)
            setattr(
                original, f"{field}_source", getattr(suspect, f"{field}_source")
            )

    # Reassign provenance rows (skip when the original already has them).
    for source in suspect.sources:
        existing = await find_source_row(
            db, original.id, source.source, source.external_id
        )
        if existing is not None:
            existing.last_seen_at = utcnow()
        else:
            source.restaurant_id = original.id

    for contact in suspect.contacts:
        contact.restaurant_id = original.id

    for presence in suspect.delivery_presence:
        stmt = select(DeliveryPresence).where(
            DeliveryPresence.restaurant_id == original.id,
            DeliveryPresence.platform == presence.platform,
        )
        existing = (await db.scalars(stmt)).first()
        if existing is not None:
            existing.url = existing.url or presence.url
            existing.last_detected_at = utcnow()
        else:
            presence.restaurant_id = original.id

    for interaction in suspect.interactions:
        interaction.restaurant_id = original.id
    for follow_up in suspect.follow_ups:
        follow_up.restaurant_id = original.id
    for generation in suspect.ai_generations:
        generation.restaurant_id = original.id

    # The original keeps its lead (1:1); the suspect's fresh lead and the
    # suspect itself are removed by cascade after the explicit user action.
    await db.delete(suspect)
