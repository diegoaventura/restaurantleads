"""API tests — Milestone 2 (auth, users, restaurants/leads CRUD, filters).

All data is fictional. Uses the throwaway test DB via the client fixture
(see conftest.py).
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.models import DeliveryPresence, Lead, Restaurant, RestaurantSource
from app.models.enums import (
    DeliveryPlatform,
    DetectionMethod,
    LeadStatus,
    SourceType,
)

BASE = "/api/v1"


async def _create_restaurant(client, headers, **overrides) -> dict:
    payload = {
        "name": "Kebab Hassan",
        "phone": "+34612345678",
        "city": "Madrid",
        "category": "kebab",
    }
    payload.update(overrides)
    response = await client.post(
        f"{BASE}/restaurants", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- health ---


async def test_health_ok(client):
    response = await client.get(f"{BASE}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert "version" in body


# --- auth ---


async def test_login_ok(client, users):
    response = await client.post(
        f"{BASE}/auth/login",
        json={"email": "ventas@example.com", "password": "sales-pass-1234"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password(client, users):
    response = await client.post(
        f"{BASE}/auth/login",
        json={"email": "ventas@example.com", "password": "wrong-pass-1234"},
    )
    assert response.status_code == 401


async def test_login_unknown_user(client):
    response = await client.post(
        f"{BASE}/auth/login",
        json={"email": "nobody@example.com", "password": "whatever-1234"},
    )
    assert response.status_code == 401


async def test_restaurants_require_auth(client):
    response = await client.get(f"{BASE}/restaurants")
    assert response.status_code == 401


async def test_invalid_token_rejected(client):
    response = await client.get(
        f"{BASE}/restaurants", headers={"Authorization": "Bearer not-a-token"}
    )
    assert response.status_code == 401


async def test_me_returns_current_user(client, auth_headers):
    response = await client.get(f"{BASE}/auth/me", headers=auth_headers["sales"])
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ventas@example.com"
    assert body["role"] == "sales"
    assert "hashed_password" not in body  # never leaked


# --- restaurants CRUD ---


async def test_create_restaurant_opens_lead_and_source(client, auth_headers):
    body = await _create_restaurant(client, auth_headers["sales"])

    assert body["name"] == "Kebab Hassan"
    assert body["lead"]["status"] == "new"  # default
    assert body["lead"]["assigned_to"] is not None
    assert [s["source"] for s in body["sources"]] == ["manual"]


async def test_get_restaurant_404(client, auth_headers):
    response = await client.get(
        f"{BASE}/restaurants/{uuid4()}", headers=auth_headers["sales"]
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Restaurante no encontrado"


async def test_patch_restaurant_marks_manual_source(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    restaurant_id = created["id"]

    response = await client.patch(
        f"{BASE}/restaurants/{restaurant_id}",
        json={"phone": "+34912345678", "category": "pizza"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "+34912345678"
    assert body["phone_source"] == "manual"  # provenance for the edit
    assert body["phone_verified_at"] is not None
    assert body["category"] == "pizza"


async def test_soft_delete_hides_restaurant(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    restaurant_id = created["id"]

    response = await client.delete(
        f"{BASE}/restaurants/{restaurant_id}", headers=auth_headers["sales"]
    )
    assert response.status_code == 200

    response = await client.get(
        f"{BASE}/restaurants/{restaurant_id}", headers=auth_headers["sales"]
    )
    assert response.status_code == 404

    response = await client.get(f"{BASE}/restaurants", headers=auth_headers["sales"])
    assert response.json()["total"] == 0


# --- listing: pagination + filters ---


async def test_list_pagination_and_city_filter(client, auth_headers):
    await _create_restaurant(client, auth_headers["sales"], name="R Madrid Uno", city="Madrid")
    await _create_restaurant(client, auth_headers["sales"], name="R Madrid Dos", city="Madrid")
    await _create_restaurant(client, auth_headers["sales"], name="R Getafe", city="Getafe")

    response = await client.get(
        f"{BASE}/restaurants", params={"city": "madrid"}, headers=auth_headers["sales"]
    )
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert all(r["city"] == "Madrid" for r in body["items"])

    response = await client.get(
        f"{BASE}/restaurants",
        params={"page": 1, "page_size": 1},
        headers=auth_headers["sales"],
    )
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["page"] == 1 and body["page_size"] == 1


async def test_list_filter_by_status_and_score(client, auth_headers, db_session):
    r1 = await _create_restaurant(client, auth_headers["sales"], name="Alto")
    r2 = await _create_restaurant(client, auth_headers["sales"], name="Bajo")

    # Direct scoring (the scoring service arrives in M4).
    lead1 = (await db_session.scalars(
        select(Lead).where(Lead.restaurant_id == r1["id"])
    )).one()
    lead1.score, lead1.status = 90, "qualified"
    lead2 = (await db_session.scalars(
        select(Lead).where(Lead.restaurant_id == r2["id"])
    )).one()
    lead2.score, lead2.status = 10, "new"
    await db_session.commit()

    response = await client.get(
        f"{BASE}/restaurants",
        params={"status": "qualified", "min_score": 50},
        headers=auth_headers["sales"],
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Alto"


async def test_list_filter_by_platform_and_source(client, auth_headers, db_session):
    created = await _create_restaurant(client, auth_headers["sales"])
    restaurant = (await db_session.scalars(
        select(Restaurant).where(Restaurant.id == created["id"])
    )).one()
    db_session.add_all(
        [
            DeliveryPresence(
                restaurant_id=restaurant.id,
                platform=DeliveryPlatform.GLOVO,
                detection_method=DetectionMethod.MANUAL,
            ),
            RestaurantSource(
                restaurant_id=restaurant.id, source=SourceType.OSM, external_id="node/1"
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        f"{BASE}/restaurants",
        params={"platform": "glovo", "source": "osm"},
        headers=auth_headers["sales"],
    )
    assert response.json()["total"] == 1

    response = await client.get(
        f"{BASE}/restaurants",
        params={"platform": "uber_eats"},
        headers=auth_headers["sales"],
    )
    assert response.json()["total"] == 0


async def test_list_sort_by_score_desc_nulls_last(client, auth_headers, db_session):
    created_high = await _create_restaurant(client, auth_headers["sales"], name="High")
    created_low = await _create_restaurant(client, auth_headers["sales"], name="Low")
    created_none = await _create_restaurant(client, auth_headers["sales"], name="SinScore")

    # Creation scores leads automatically (M4): set explicit scores so the
    # sort is deterministic, including an unscored (None) lead.
    for created, score in ((created_high, 10), (created_low, 90), (created_none, None)):
        lead = (await db_session.scalars(
            select(Lead).where(Lead.restaurant_id == created["id"])
        )).one()
        lead.score = score
    await db_session.commit()

    response = await client.get(
        f"{BASE}/restaurants",
        params={"sort": "score", "order": "desc"},
        headers=auth_headers["sales"],
    )
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["Low", "High", "SinScore"]  # unscored last


# --- lead state machine ---


async def test_lead_valid_transition(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    response = await client.patch(
        f"{BASE}/restaurants/{created['id']}/lead",
        json={"status": "qualified"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 200
    assert response.json()["status"] == "qualified"


async def test_lead_invalid_transition_sales_forbidden(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    response = await client.patch(
        f"{BASE}/restaurants/{created['id']}/lead",
        json={"status": "customer"},  # new -> customer is out of the table
        headers=auth_headers["sales"],
    )
    assert response.status_code == 422
    assert "Transición inválida" in response.json()["detail"]


async def test_lead_invalid_transition_admin_allowed(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    response = await client.patch(
        f"{BASE}/restaurants/{created['id']}/lead",
        json={"status": "customer"},
        headers=auth_headers["admin"],  # admin may override the table
    )
    assert response.status_code == 200
    assert response.json()["status"] == "customer"


async def test_lead_assign_unknown_user_404(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    response = await client.patch(
        f"{BASE}/restaurants/{created['id']}/lead",
        json={"assigned_to": str(uuid4())},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 404


# --- users (admin only) ---


async def test_users_require_admin(client, auth_headers):
    response = await client.get(f"{BASE}/users", headers=auth_headers["sales"])
    assert response.status_code == 403


async def test_users_admin_crud_and_duplicate_email_409(client, auth_headers):
    response = await client.get(f"{BASE}/users", headers=auth_headers["admin"])
    assert response.status_code == 200
    assert response.json()["total"] == 2  # admin + sales from the fixture

    response = await client.post(
        f"{BASE}/users",
        json={
            "email": "nuevo@example.com",
            "full_name": "Nueva Persona",
            "password": "nuevo-pass-1234",
            "role": "sales",
        },
        headers=auth_headers["admin"],
    )
    assert response.status_code == 201
    new_user_id = response.json()["id"]
    assert response.json()["role"] == "sales"

    # Duplicate email -> 409 via the IntegrityError handler.
    response = await client.post(
        f"{BASE}/users",
        json={
            "email": "nuevo@example.com",
            "full_name": "Duplicado",
            "password": "nuevo-pass-1234",
        },
        headers=auth_headers["admin"],
    )
    assert response.status_code == 409

    response = await client.patch(
        f"{BASE}/users/{new_user_id}",
        json={"is_active": False},
        headers=auth_headers["admin"],
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_inactive_user_cannot_authenticate(client, auth_headers):
    # Deactivate the sales user via admin.
    users_response = await client.get(
        f"{BASE}/users", params={"page_size": 100}, headers=auth_headers["admin"]
    )
    sales_user = next(
        u for u in users_response.json()["items"] if u["email"] == "ventas@example.com"
    )
    await client.patch(
        f"{BASE}/users/{sales_user['id']}",
        json={"is_active": False},
        headers=auth_headers["admin"],
    )

    # The existing token stops working (user checked per request).
    response = await client.get(f"{BASE}/auth/me", headers=auth_headers["sales"])
    assert response.status_code == 401

    # And a new login is rejected too.
    response = await client.post(
        f"{BASE}/auth/login",
        json={"email": "ventas@example.com", "password": "sales-pass-1234"},
    )
    assert response.status_code == 401
