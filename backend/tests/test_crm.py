"""CRM tests: interactions (append-only, status sync) and follow-ups."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest

from app.db.base import utcnow
from tests.test_api import BASE, _create_restaurant

OCT3 = datetime(2026, 10, 3, 11, 20, tzinfo=UTC)
OCT6 = datetime(2026, 10, 6, 11, 20, tzinfo=UTC)


async def _register(client, headers, restaurant_id, result, **overrides):
    payload = {
        "channel": "call",
        "result": result,
        "occurred_at": "2026-10-03T11:20:00Z",
    }
    payload.update(overrides)
    response = await client.post(
        f"{BASE}/restaurants/{restaurant_id}/interactions",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- interactions: status sync + auto follow-ups ---


async def test_no_answer_syncs_status_and_creates_follow_up(client, auth_headers):
    """The plan's core example: call 03/10 no_answer -> follow-up 06/10."""
    created = await _create_restaurant(client, auth_headers["sales"])

    body = await _register(
        client, auth_headers["sales"], created["id"], "no_answer", notes="Tono de ocupado"
    )

    assert body["interaction"]["result"] == "no_answer"
    assert body["lead_status"] == "no_response"  # synced automatically
    follow_up = body["follow_up_created"]
    assert follow_up is not None
    assert follow_up["scheduled_at"] == "2026-10-06T11:20:00Z"  # +3 days
    assert follow_up["status"] == "pending"
    assert follow_up["channel"] == "call"


async def test_callback_requested_follow_up_next_day(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    body = await _register(
        client, auth_headers["sales"], created["id"], "callback_requested"
    )
    assert body["follow_up_created"]["scheduled_at"] == "2026-10-04T11:20:00Z"


async def test_interested_no_follow_up_and_status_synced(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    body = await _register(client, auth_headers["sales"], created["id"], "interested")

    assert body["lead_status"] == "interested"
    assert body["follow_up_created"] is None


async def test_status_sync_bridges_through_contacted(client, auth_headers):
    """no_response -> interested is not direct; sync bridges via contacted."""
    created = await _create_restaurant(client, auth_headers["sales"])
    await _register(client, auth_headers["sales"], created["id"], "no_answer")

    body = await _register(client, auth_headers["sales"], created["id"], "interested")
    assert body["lead_status"] == "interested"


async def test_status_sync_skipped_on_terminal_leads(client, auth_headers):
    """A customer stays a customer; the interaction is still recorded."""
    created = await _create_restaurant(client, auth_headers["sales"])
    await client.patch(
        f"{BASE}/restaurants/{created['id']}/lead",
        json={"status": "customer"},
        headers=auth_headers["admin"],  # admin override to reach terminal fast
    )

    body = await _register(client, auth_headers["sales"], created["id"], "no_answer")
    assert body["interaction"]["result"] == "no_answer"
    assert body["lead_status"] == "customer"  # untouched


async def test_interactions_404_for_unknown_restaurant(client, auth_headers):
    import uuid

    response = await client.post(
        f"{BASE}/restaurants/{uuid.uuid4()}/interactions",
        json={"channel": "call", "result": "no_answer"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 404


# --- interactions: history ---


async def test_interaction_history_is_chronological_and_immutable(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    restaurant_id = created["id"]

    await _register(client, auth_headers["sales"], restaurant_id, "no_answer",
                    occurred_at="2026-10-01T09:00:00Z")
    await _register(client, auth_headers["sales"], restaurant_id, "no_answer",
                    occurred_at="2026-10-03T11:20:00Z")
    await _register(client, auth_headers["sales"], restaurant_id, "callback_requested",
                    occurred_at="2026-10-05T10:00:00Z")

    response = await client.get(
        f"{BASE}/restaurants/{restaurant_id}/interactions",
        headers=auth_headers["sales"],
    )
    body = response.json()
    assert body["total"] == 3
    dates = [i["occurred_at"] for i in body["items"]]
    assert dates == sorted(dates, reverse=True)  # most recent first

    # No update/delete routes exist: history is append-only.
    response = await client.delete(
        f"{BASE}/restaurants/{restaurant_id}/interactions",
        headers=auth_headers["admin"],
    )
    assert response.status_code == 405


# --- follow-ups: agenda ---


async def _create_follow_up(client, headers, restaurant_id, scheduled_at, **overrides):
    payload = {"scheduled_at": scheduled_at, "channel": "call"}
    payload.update(overrides)
    response = await client.post(
        f"{BASE}/restaurants/{restaurant_id}/follow-ups",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_manual_follow_up_and_nested_list(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    await _create_follow_up(
        client, auth_headers["sales"], created["id"], "2026-10-10T09:00:00Z"
    )

    response = await client.get(
        f"{BASE}/restaurants/{created['id']}/follow-ups",
        headers=auth_headers["sales"],
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "pending"
    assert body["items"][0]["restaurant_name"] == "Kebab Hassan"


async def test_due_today_filter(client, auth_headers):
    today = utcnow().date()
    tomorrow = today + timedelta(days=1)
    r_today = await _create_restaurant(client, auth_headers["sales"], name="Hoy")
    r_tomorrow = await _create_restaurant(client, auth_headers["sales"], name="Manana")

    at = lambda d: datetime.combine(d, time(10), tzinfo=UTC).isoformat()
    await _create_follow_up(client, auth_headers["sales"], r_today["id"], at(today))
    await _create_follow_up(client, auth_headers["sales"], r_tomorrow["id"], at(tomorrow))

    # Global agenda: pending + due today -> exactly one.
    response = await client.get(
        f"{BASE}/follow-ups",
        params={"status": "pending", "due_on": today.isoformat()},
        headers=auth_headers["sales"],
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["restaurant_name"] == "Hoy"

    # due_before (inclusive of that day) catches both.
    response = await client.get(
        f"{BASE}/follow-ups",
        params={"due_before": tomorrow.isoformat()},
        headers=auth_headers["sales"],
    )
    assert response.json()["total"] == 2

    # Pending only (no date): both.
    response = await client.get(
        f"{BASE}/follow-ups",
        params={"status": "pending"},
        headers=auth_headers["sales"],
    )
    assert response.json()["total"] == 2


# --- follow-ups: actions (test_follow_up_status) ---


async def test_follow_up_complete(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    follow_up = await _create_follow_up(
        client, auth_headers["sales"], created["id"], "2026-10-10T09:00:00Z"
    )

    response = await client.patch(
        f"{BASE}/follow-ups/{follow_up['id']}",
        json={"action": "complete", "notes": "Hablamos; interesado"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None
    assert "Hablamos; interesado" in body["notes"]  # note appended

    # Acting again on a completed follow-up is rejected.
    response = await client.patch(
        f"{BASE}/follow-ups/{follow_up['id']}",
        json={"action": "complete"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 422


async def test_follow_up_postpone_requires_new_date(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    follow_up = await _create_follow_up(
        client, auth_headers["sales"], created["id"], "2026-10-10T09:00:00Z"
    )

    response = await client.patch(
        f"{BASE}/follow-ups/{follow_up['id']}",
        json={"action": "postpone"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 422


async def test_follow_up_postpone_moves_date_stays_pending(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    follow_up = await _create_follow_up(
        client, auth_headers["sales"], created["id"], "2026-10-10T09:00:00Z"
    )

    response = await client.patch(
        f"{BASE}/follow-ups/{follow_up['id']}",
        json={"action": "postpone", "new_date": "2026-10-13T09:00:00Z",
              "notes": "Lo pide el dueño"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"  # still open, on the new date
    assert body["scheduled_at"] == "2026-10-13T09:00:00Z"

    listing = await client.get(
        f"{BASE}/follow-ups",
        params={"status": "pending"},
        headers=auth_headers["sales"],
    )
    assert listing.json()["total"] == 1  # still on the agenda


async def test_follow_up_cancel(client, auth_headers):
    created = await _create_restaurant(client, auth_headers["sales"])
    follow_up = await _create_follow_up(
        client, auth_headers["sales"], created["id"], "2026-10-10T09:00:00Z"
    )

    response = await client.patch(
        f"{BASE}/follow-ups/{follow_up['id']}",
        json={"action": "cancel", "notes": "Ya es cliente"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    listing = await client.get(
        f"{BASE}/follow-ups",
        params={"status": "pending"},
        headers=auth_headers["sales"],
    )
    assert listing.json()["total"] == 0


async def test_follow_up_actions_404(client, auth_headers):
    import uuid

    response = await client.patch(
        f"{BASE}/follow-ups/{uuid.uuid4()}",
        json={"action": "complete"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 404


async def test_follow_up_no_delete_route(client, auth_headers):
    import uuid

    response = await client.delete(
        f"{BASE}/follow-ups/{uuid.uuid4()}",
        headers=auth_headers["admin"],
    )
    assert response.status_code == 405  # complete/cancel, never delete
