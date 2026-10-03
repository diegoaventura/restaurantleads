"""Minimal development seed — FICTIONAL data only.

Usage (from backend/):
    python scripts/seed.py

Creates 2 internal users and 3 fictional restaurants with sources,
delivery presence, contacts, leads, interactions and follow-ups so the
schema can be explored by hand. NEVER use real personal data here.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bcrypt
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.eventloop import ensure_compatible_event_loop
from app.db.base import utcnow
from app.models import (
    AIGeneration,
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
    LeadPriority,
    LeadStatus,
    SourceType,
    UserRole,
)

DEMO_PASSWORD = "demo1234"  # fictional, dev-only


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


async def main() -> None:
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # Wipe existing data (dev convenience; FK-safe order).
        for model in (
            AIGeneration,
            FollowUp,
            Interaction,
            Lead,
            Contact,
            DeliveryPresence,
            RestaurantSource,
            Restaurant,
            User,
        ):
            await session.execute(delete(model))

        # --- Users (fictional) ---
        admin = User(
            email="admin@demo.local",
            full_name="Ana Admin",
            hashed_password=hash_password(DEMO_PASSWORD),
            role=UserRole.ADMIN,
        )
        sales = User(
            email="ventas@demo.local",
            full_name="Sam Sales",
            hashed_password=hash_password(DEMO_PASSWORD),
            role=UserRole.SALES,
        )
        session.add_all([admin, sales])
        await session.flush()

        # --- Restaurant 1: everything filled in ---
        kebab = Restaurant(
            name="Kebab Hassan",
            normalized_name="kebab hassan",
            phone="+34612345678",
            phone_source=SourceType.OSM,
            website="kebabhassan.example",
            website_source=SourceType.OSM,
            city="Madrid",
            postal_code="28012",
            address="Calle Example 1",
            latitude=40.416775,
            longitude=-3.70379,
            category="kebab",
        )
        session.add(kebab)
        await session.flush()
        session.add_all(
            [
                RestaurantSource(
                    restaurant_id=kebab.id,
                    source=SourceType.OSM,
                    external_id="node/9876543",
                ),
                DeliveryPresence(
                    restaurant_id=kebab.id,
                    platform=DeliveryPlatform.GLOVO,
                    detection_method=DetectionMethod.WEBSITE_LINK,
                    url="https://glovoapp.example/es/madrid/kebab-hassan",
                ),
                Contact(
                    restaurant_id=kebab.id,
                    contact_type=ContactType.PHONE,
                    value="+34612345678",
                    source=SourceType.OSM,
                    verified=True,
                ),
                Lead(
                    restaurant_id=kebab.id,
                    score=87,
                    score_reasons=[
                        {"factor": "delivery_detectado", "points": 25},
                        {"factor": "zona_cubierta", "points": 20},
                        {"factor": "telefono_disponible", "points": 10},
                    ],
                    status=LeadStatus.CONTACTED,
                    priority=LeadPriority.HIGH,
                    assigned_to=sales.id,
                ),
                Interaction(
                    restaurant_id=kebab.id,
                    channel=InteractionChannel.CALL,
                    result=InteractionResult.NO_ANSWER,
                    notes="Llamada a las 11:20, sin respuesta",
                    created_by=sales.id,
                ),
                FollowUp(
                    restaurant_id=kebab.id,
                    scheduled_at=utcnow() + timedelta(days=3),
                    channel=InteractionChannel.CALL,
                    status=FollowUpStatus.PENDING,
                    created_by=sales.id,
                ),
            ]
        )

        # --- Restaurant 2: sparse, new lead ---
        pizzeria = Restaurant(
            name="Pizzeria Napoli Vera",
            normalized_name="pizzeria napoli vera",
            phone="+34912345678",
            phone_source=SourceType.MANUAL_IMPORT,
            city="Getafe",
            postal_code="28901",
            category="pizza",
        )
        session.add(pizzeria)
        await session.flush()
        session.add_all(
            [
                RestaurantSource(restaurant_id=pizzeria.id, source=SourceType.MANUAL_IMPORT),
                Lead(restaurant_id=pizzeria.id, score=42, status=LeadStatus.NEW),
            ]
        )

        # --- Restaurant 3: interested, on just_eat ---
        sushi = Restaurant(
            name="Sushi Kaizen",
            normalized_name="sushi kaizen",
            phone="+34931234567",
            email="hola@sushikaizen.example",
            website="sushikaizen.example",
            city="Barcelona",
            postal_code="08001",
            category="japanese",
        )
        session.add(sushi)
        await session.flush()
        session.add_all(
            [
                RestaurantSource(
                    restaurant_id=sushi.id,
                    source=SourceType.OSM,
                    external_id="node/2468001",
                ),
                DeliveryPresence(
                    restaurant_id=sushi.id,
                    platform=DeliveryPlatform.JUST_EAT,
                    detection_method=DetectionMethod.WEBSITE_LINK,
                ),
                Contact(
                    restaurant_id=sushi.id,
                    contact_type=ContactType.EMAIL,
                    value="hola@sushikaizen.example",
                    source=SourceType.OSM,
                ),
                Lead(
                    restaurant_id=sushi.id,
                    score=72,
                    status=LeadStatus.INTERESTED,
                    priority=LeadPriority.HIGH,
                    assigned_to=sales.id,
                ),
                Interaction(
                    restaurant_id=sushi.id,
                    channel=InteractionChannel.CALL,
                    result=InteractionResult.MEETING_SCHEDULED,
                    notes="Reunion propuesta el proximo martes",
                    created_by=sales.id,
                ),
            ]
        )

        await session.commit()

    await engine.dispose()
    print("Seed OK: 2 usuarios (admin@demo.local / ventas@demo.local, pass: demo1234)")
    print("Seed OK: 3 restaurantes ficticios con leads, interacciones y seguimientos")


if __name__ == "__main__":
    ensure_compatible_event_loop()
    asyncio.run(main())
