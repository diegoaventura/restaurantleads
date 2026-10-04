"""Tests: GDPR export + assignable users (Milestone 7)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.models import DeliveryPresence, Restaurant
from app.models.enums import DeliveryPlatform, DetectionMethod
from tests.test_api import BASE, _create_restaurant


async def _add_delivery(db_session, restaurant_id):
    db_session.add(
        DeliveryPresence(
            restaurant_id=restaurant_id,
            platform=DeliveryPlatform.GLOVO,
            detection_method=DetectionMethod.WEBSITE_LINK,
            url="https://glovoapp.example/kebab",
        )
    )
    await db_session.commit()


async def test_export_requires_auth(client):
    response = await client.get(f"{BASE}/restaurants/{uuid4()}/export")
    assert response.status_code == 401


async def test_export_unknown_restaurant_404(client, auth_headers):
    response = await client.get(
        f"{BASE}/restaurants/{uuid4()}/export", headers=auth_headers["sales"]
    )
    assert response.status_code == 404


async def test_export_returns_complete_record(client, auth_headers, db_session):
    headers = auth_headers["sales"]
    created = await _create_restaurant(client, headers)
    await _add_delivery(db_session, created["id"])
    await client.post(
        f"{BASE}/restaurants/{created['id']}/interactions",
        json={"channel": "call", "result": "no_answer", "notes": "Sin respuesta"},
        headers=headers,
    )

    response = await client.get(
        f"{BASE}/restaurants/{created['id']}/export", headers=headers
    )
    assert response.status_code == 200
    body = response.json()

    assert body["exported_at"]
    restaurant = body["restaurant"]
    assert restaurant["name"] == "Kebab Hassan"
    assert restaurant["phone"] == "+34612345678"
    assert restaurant["phone_source"] == "manual"  # provenance included
    assert [s["source"] for s in restaurant["sources"]] == ["manual"]
    assert restaurant["delivery_presence"][0]["platform"] == "glovo"
    assert restaurant["delivery_presence"][0]["url"]
    assert len(restaurant["interactions"]) == 1
    assert len(restaurant["follow_ups"]) == 1  # the automatic one (+3 days)
    assert restaurant["lead"]["status"] == "no_response"  # synced by the interaction


async def test_export_excludes_soft_deleted(client, auth_headers):
    headers = auth_headers["sales"]
    created = await _create_restaurant(client, headers)
    await client.delete(f"{BASE}/restaurants/{created['id']}", headers=headers)

    response = await client.get(
        f"{BASE}/restaurants/{created['id']}/export", headers=headers
    )
    assert response.status_code == 404


async def test_assignable_users_minimal_fields(client, auth_headers):
    headers = auth_headers["sales"]
    response = await client.get(f"{BASE}/users/assignable", headers=headers)
    assert response.status_code == 200
    users = response.json()

    assert len(users) == 2  # admin + sales (both active)
    assert all(set(u.keys()) == {"id", "full_name", "role"} for u in users)
    assert all("email" not in u for u in users)  # no emails for privacy

    # Deactivate one -> it disappears from the assignable list.
    listing = await client.get(
        f"{BASE}/users", params={"page_size": 100}, headers=auth_headers["admin"]
    )
    sales_user = next(
        u for u in listing.json()["items"] if u["email"] == "ventas@example.com"
    )
    await client.patch(
        f"{BASE}/users/{sales_user['id']}",
        json={"is_active": False},
        headers=auth_headers["admin"],
    )
    response = await client.get(f"{BASE}/users/assignable", headers=headers)
    assert len(response.json()) == 1
