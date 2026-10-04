"""Dashboard stats tests (plan FASE 8 KPIs)."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from app.db.base import utcnow
from tests.test_api import BASE, _create_restaurant


async def test_stats_requires_auth(client):
    response = await client.get(f"{BASE}/dashboard/stats")
    assert response.status_code == 401


async def test_stats_counts_and_row_fields(client, auth_headers, db_session):
    from sqlalchemy import select

    from app.models import DeliveryPresence, Lead, Restaurant
    from app.models.enums import (
        DeliveryPlatform,
        DetectionMethod,
        FollowUpStatus,
        LeadStatus,
    )

    headers = auth_headers["sales"]
    # 3 restaurants via API: one stays new, two get worked.
    r_new = await _create_restaurant(client, headers, name="Nuevo Uno")
    r_contacted = await _create_restaurant(client, headers, name="Contactado Uno")
    r_customer = await _create_restaurant(client, headers, name="Cliente Uno")

    # Contacted -> no_response with an auto follow-up due today (+3d) ->
    # moved to today directly for the "due today" counter.
    await client.post(
        f"{BASE}/restaurants/{r_contacted['id']}/interactions",
        json={"channel": "call", "result": "no_answer"},
        headers=headers,
    )
    agenda = await client.get(
        f"{BASE}/follow-ups", params={"status": "pending"}, headers=headers
    )
    follow_up_id = agenda.json()["items"][0]["id"]
    today_at = datetime.combine(utcnow().date(), time(12), tzinfo=UTC)
    await client.patch(
        f"{BASE}/follow-ups/{follow_up_id}",
        json={"action": "postpone", "new_date": today_at.isoformat()},
        headers=headers,
    )

    # Customer via admin override (fast path to the terminal status).
    await client.patch(
        f"{BASE}/restaurants/{r_customer['id']}/lead",
        json={"status": "customer"},
        headers=auth_headers["admin"],
    )
    # Delivery presence on the new one (list-row derived fields).
    restaurant = (await db_session.scalars(
        select(Restaurant).where(Restaurant.id == r_new["id"])
    )).one()
    db_session.add(
        DeliveryPresence(
            restaurant_id=restaurant.id,
            platform=DeliveryPlatform.GLOVO,
            detection_method=DetectionMethod.MANUAL,
        )
    )
    await db_session.commit()

    response = await client.get(f"{BASE}/dashboard/stats", headers=headers)
    assert response.status_code == 200
    stats = response.json()

    assert stats["restaurants_total"] == 3
    assert stats["leads_total"] == 3
    assert stats["leads_new"] == 1
    assert stats["pending_contact"] == 1
    assert stats["follow_ups_due_today"] == 1
    assert stats["follow_ups_overdue"] == 0
    assert stats["customers"] == 1
    assert stats["conversion_rate"] == round(1 / 3, 4)

    # List rows expose the derived fields for the table columns.
    listing = await client.get(f"{BASE}/restaurants", headers=headers)
    rows = {item["name"]: item for item in listing.json()["items"]}
    assert rows["Nuevo Uno"]["delivery_platforms"] == ["glovo"]
    assert rows["Contactado Uno"]["last_interaction_at"] is not None
    assert rows["Contactado Uno"]["next_follow_up_at"] is not None
    assert rows["Nuevo Uno"]["last_interaction_at"] is None
    assert rows["Cliente Uno"]["next_follow_up_at"] is None


async def test_stats_overdue_follow_ups(client, auth_headers):
    from datetime import datetime as dt

    headers = auth_headers["sales"]
    created = await _create_restaurant(client, headers)
    yesterday = dt.combine(
        utcnow().date() - timedelta(days=1), time(9), tzinfo=UTC
    )
    await client.post(
        f"{BASE}/restaurants/{created['id']}/follow-ups",
        json={"scheduled_at": yesterday.isoformat(), "channel": "call"},
        headers=headers,
    )

    stats = (
        await client.get(f"{BASE}/dashboard/stats", headers=headers)
    ).json()
    assert stats["follow_ups_overdue"] == 1
    assert stats["follow_ups_due_today"] == 0


async def test_stats_empty_database(client, auth_headers):
    stats = (
        await client.get(
            f"{BASE}/dashboard/stats", headers=auth_headers["sales"]
        )
    ).json()
    assert stats["restaurants_total"] == 0
    assert stats["leads_total"] == 0
    assert stats["conversion_rate"] == 0.0  # no division by zero
