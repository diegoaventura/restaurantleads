"""Model/migration tests — Milestone 1.

These run against the throwaway `restaurant_leads_test` database created by
running the REAL Alembic migrations (see conftest.py), so they also verify
constraints and indexes at the PostgreSQL level.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Contact,
    DeliveryPresence,
    FollowUp,
    Interaction,
    Lead,
    Restaurant,
    RestaurantSource,
    User,
)
from app.models.enums import (
    ContactType,
    DeliveryPlatform,
    DetectionMethod,
    FollowUpStatus,
    InteractionChannel,
    InteractionResult,
    LeadStatus,
    SourceType,
)


async def _make_restaurant(
    db_session, name: str = "Kebab Hassan", **kwargs
) -> Restaurant:
    restaurant = Restaurant(name=name, normalized_name=name.lower(), **kwargs)
    db_session.add(restaurant)
    await db_session.commit()
    await db_session.refresh(restaurant)
    return restaurant


async def test_restaurant_and_lead_roundtrip(db_session):
    restaurant = await _make_restaurant(db_session, phone="+34612345678", city="Madrid")
    lead = Lead(
        restaurant_id=restaurant.id,
        score=87,
        score_reasons=[{"factor": "delivery_detectado", "points": 25}],
    )
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)

    assert lead.id is not None
    assert lead.status == LeadStatus.NEW  # default
    assert lead.priority is not None
    assert lead.created_at is not None and lead.updated_at is not None


async def test_lead_is_one_to_one_with_restaurant(db_session):
    restaurant = await _make_restaurant(db_session)
    db_session.add(Lead(restaurant_id=restaurant.id, score=10))
    await db_session.commit()
    db_session.add(Lead(restaurant_id=restaurant.id, score=20))

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_lead_score_check_constraint(db_session):
    restaurant = await _make_restaurant(db_session)
    db_session.add(Lead(restaurant_id=restaurant.id, score=150))

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_restaurant_source_unique_constraint(db_session):
    restaurant = await _make_restaurant(db_session)
    db_session.add_all(
        [
            RestaurantSource(
                restaurant_id=restaurant.id, source=SourceType.OSM, external_id="node/1"
            ),
            RestaurantSource(
                restaurant_id=restaurant.id, source=SourceType.OSM, external_id="node/2"
            ),
            RestaurantSource(
                restaurant_id=restaurant.id, source=SourceType.MANUAL_IMPORT
            ),
        ]
    )
    await db_session.commit()

    # Same restaurant + source + external_id twice → rejected.
    db_session.add(
        RestaurantSource(
            restaurant_id=restaurant.id, source=SourceType.OSM, external_id="node/1"
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_restaurant_source_nulls_not_distinct(db_session):
    """NULLS NOT DISTINCT: two NULL external_ids for the same pair collide."""
    restaurant = await _make_restaurant(db_session)
    db_session.add(
        RestaurantSource(restaurant_id=restaurant.id, source=SourceType.MANUAL_IMPORT)
    )
    await db_session.commit()

    db_session.add(
        RestaurantSource(restaurant_id=restaurant.id, source=SourceType.MANUAL_IMPORT)
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_delivery_presence_unique_per_platform(db_session):
    restaurant = await _make_restaurant(db_session)
    db_session.add(
        DeliveryPresence(
            restaurant_id=restaurant.id,
            platform=DeliveryPlatform.GLOVO,
            detection_method=DetectionMethod.WEBSITE_LINK,
        )
    )
    await db_session.commit()

    db_session.add(
        DeliveryPresence(
            restaurant_id=restaurant.id,
            platform=DeliveryPlatform.GLOVO,
            detection_method=DetectionMethod.MANUAL,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_user_email_unique(db_session):
    db_session.add(
        User(
            email="admin@demo.local",
            full_name="Ana Admin",
            hashed_password="not-a-real-hash",
        )
    )
    await db_session.commit()

    db_session.add(
        User(
            email="admin@demo.local",
            full_name="Otra Ana",
            hashed_password="not-a-real-hash",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_delete_restaurant_cascades_children(db_session):
    restaurant = await _make_restaurant(db_session)
    db_session.add_all(
        [
            RestaurantSource(
                restaurant_id=restaurant.id, source=SourceType.OSM, external_id="node/9"
            ),
            DeliveryPresence(
                restaurant_id=restaurant.id,
                platform=DeliveryPlatform.GLOVO,
                detection_method=DetectionMethod.MANUAL,
            ),
            Contact(
                restaurant_id=restaurant.id,
                contact_type=ContactType.PHONE,
                value="+34612345678",
                source=SourceType.OSM,
            ),
            Interaction(
                restaurant_id=restaurant.id,
                channel=InteractionChannel.CALL,
                result=InteractionResult.NO_ANSWER,
            ),
            Lead(restaurant_id=restaurant.id, score=50),
            FollowUp(
                restaurant_id=restaurant.id,
                scheduled_at=datetime(2026, 10, 6, 9, tzinfo=UTC),
                channel=InteractionChannel.CALL,
            ),
        ]
    )
    await db_session.commit()

    await db_session.delete(restaurant)
    await db_session.commit()

    for model in (
        RestaurantSource,
        DeliveryPresence,
        Contact,
        Interaction,
        Lead,
        FollowUp,
    ):
        rows = await db_session.scalars(select(model))
        assert rows.first() is None, f"{model.__name__} rows should have been cascaded"


async def test_possible_duplicate_self_reference(db_session):
    original = await _make_restaurant(db_session, name="Kebab Hassan")
    suspect = await _make_restaurant(db_session, name="Kebab Hassan ")
    suspect.possible_duplicate_of_id = original.id
    await db_session.commit()
    await db_session.refresh(suspect)

    assert suspect.possible_duplicate_of_id == original.id


async def test_follow_up_default_status_pending(db_session):
    restaurant = await _make_restaurant(db_session)
    follow_up = FollowUp(
        restaurant_id=restaurant.id,
        scheduled_at=datetime(2026, 10, 6, 9, tzinfo=UTC),
        channel=InteractionChannel.CALL,
    )
    db_session.add(follow_up)
    await db_session.commit()
    await db_session.refresh(follow_up)

    assert follow_up.status == FollowUpStatus.PENDING
    assert follow_up.completed_at is None
