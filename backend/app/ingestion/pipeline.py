"""Ingestion pipeline: extract → normalize → validate → deduplicate → load.

Connectors only extract; everything else happens here so every source
follows exactly the same rules. `dry_run=True` executes the whole pipeline
and rolls back, so counters are real without touching the database.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.ingestion.base import Connector
from app.models import Lead, Restaurant, RestaurantSource
from app.schemas.ingestion import (
    IngestionRunResult,
    PossibleDuplicateDetail,
    RestaurantCandidate,
)
from app.services import dedup
from app.services.normalization import (
    normalize_candidate,
    normalize_name,
    validate_candidate,
)

MAX_INVALID_REASONS_RETURNED = 20


async def run_ingestion(
    db: AsyncSession, connector: Connector, *, dry_run: bool = False
) -> IngestionRunResult:
    received = 0
    invalid = 0
    new = 0
    exact_duplicates = 0
    possible_duplicates = 0
    invalid_reasons: list[str] = []
    possible_details: list[PossibleDuplicateDetail] = []

    candidates = await connector.fetch()

    for candidate in candidates:
        received += 1

        normalized, errors = normalize_candidate(candidate)
        reasons = errors + validate_candidate(normalized)
        if reasons:
            invalid += 1
            invalid_reasons.extend(
                f"[{candidate.source.value}] {reason}" for reason in reasons
            )
            continue

        match = await dedup.find_match(db, normalized)

        if match.type is dedup.MatchType.EXACT:
            assert match.restaurant is not None
            await _merge_into_existing(db, match.restaurant, normalized)
            exact_duplicates += 1
        else:
            restaurant = _create_restaurant(db, normalized)
            new += 1
            if match.type is dedup.MatchType.POSSIBLE and match.restaurant:
                # Uncertain match: create, flag and queue for human review.
                restaurant.possible_duplicate_of_id = match.restaurant.id
                possible_duplicates += 1
                possible_details.append(
                    PossibleDuplicateDetail(
                        restaurant_id=restaurant.id,
                        name=restaurant.name,
                        duplicate_of_id=match.restaurant.id,
                        duplicate_of_name=match.restaurant.name,
                        criterion=match.criterion,
                    )
                )

    if dry_run:
        await db.rollback()
    else:
        await db.commit()

    return IngestionRunResult(
        run_id=uuid.uuid4(),
        connector=connector.name,
        dry_run=dry_run,
        received=received,
        valid=received - invalid,
        new=new,
        exact_duplicates=exact_duplicates,
        possible_duplicates=possible_duplicates,
        invalid=invalid,
        invalid_reasons=invalid_reasons[:MAX_INVALID_REASONS_RETURNED],
        possible_duplicate_details=possible_details,
    )


async def _merge_into_existing(
    db: AsyncSession, restaurant: Restaurant, candidate: RestaurantCandidate
) -> None:
    """Confident match: fill missing fields only, refresh provenance.

    Existing data is NEVER silently overwritten (docs/DATABASE.md).
    """
    now = utcnow()
    for field in (
        "address",
        "city",
        "postal_code",
        "latitude",
        "longitude",
        "category",
    ):
        value = getattr(candidate, field)
        if getattr(restaurant, field) is None and value is not None:
            setattr(restaurant, field, value)
    for field in ("phone", "email", "website"):
        value = getattr(candidate, field)
        if getattr(restaurant, field) is None and value is not None:
            setattr(restaurant, field, value)
            setattr(restaurant, f"{field}_source", candidate.source)
            setattr(restaurant, f"{field}_verified_at", None)

    source_row = await dedup.find_source_row(
        db, restaurant.id, candidate.source, candidate.external_id
    )
    if source_row is not None:
        source_row.last_seen_at = now
    else:
        db.add(
            RestaurantSource(
                restaurant_id=restaurant.id,
                source=candidate.source,
                source_url=candidate.source_url,
                external_id=candidate.external_id,
            )
        )


def _create_restaurant(
    db: AsyncSession, candidate: RestaurantCandidate
) -> Restaurant:
    """No match: create the restaurant + provenance + lead (status NEW)."""
    assert candidate.name is not None  # validated above
    restaurant = Restaurant(
        id=uuid.uuid4(),  # available immediately (no flush needed yet)
        name=candidate.name,
        normalized_name=normalize_name(candidate.name),
        phone=candidate.phone,
        phone_source=candidate.source if candidate.phone else None,
        email=candidate.email,
        email_source=candidate.source if candidate.email else None,
        website=candidate.website,
        website_source=candidate.source if candidate.website else None,
        address=candidate.address,
        city=candidate.city,
        postal_code=candidate.postal_code,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        category=candidate.category,
    )
    restaurant.sources = [
        RestaurantSource(
            source=candidate.source,
            source_url=candidate.source_url,
            external_id=candidate.external_id,
        )
    ]
    restaurant.lead = Lead()  # unassigned pool, status NEW
    db.add(restaurant)
    return restaurant
