"""Ingestion API tests: CSV connector, dry_run, duplicates queue and resolve."""

from __future__ import annotations

BASE = "/api/v1"

# Fictional CSV for the manual_import connector (NEVER real data).
SAMPLE_CSV = """name,phone,email,website,address,city,postal_code,category,latitude,longitude
Kebab Nuevo,+34 611 222 333,hola@kebabnuevo.example,kebabnuevo.example,Calle Ficticia 5,Alcobendas,28100,kebab,40.547000,-3.635000
Kebab Duplicado,+34612345678,,kebabexistente.example,Calle Inventada 9,Madrid,28012,kebab,,
,info@sinnombre.example,,,,,,,,
Kebab Nuvvo,+34 611 222 334,,kebabnuvvo.example,Calle Ficticia 6,Alcobendas,28100,kebab,40.547050,-3.634950
"""


async def _run_ingestion(client, headers, csv_content: str, dry_run: bool):
    response = await client.post(
        f"{BASE}/ingestion/run",
        json={
            "connector": "manual_import",
            "params": {"csv_content": csv_content},
            "dry_run": dry_run,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _create_existing_restaurant(client, headers):
    response = await client.post(
        f"{BASE}/restaurants",
        json={"name": "Kebab Existente", "phone": "+34612345678", "city": "Madrid"},
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def test_ingestion_run_requires_admin(client, auth_headers):
    response = await client.post(
        f"{BASE}/ingestion/run",
        json={"connector": "manual_import", "params": {"csv_content": SAMPLE_CSV}},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 403


async def test_connectors_listed(client, auth_headers):
    response = await client.get(
        f"{BASE}/ingestion/connectors", headers=auth_headers["admin"]
    )
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["manual_import", "osm"]


async def test_unknown_connector_404(client, auth_headers):
    response = await client.post(
        f"{BASE}/ingestion/run",
        json={"connector": "no-existe", "params": {}},
        headers=auth_headers["admin"],
    )
    assert response.status_code == 404


async def test_manual_import_dry_run_writes_nothing(client, auth_headers):
    await _create_existing_restaurant(client, auth_headers["admin"])

    result = await _run_ingestion(client, auth_headers["admin"], SAMPLE_CSV, dry_run=True)

    # 4 received: 1 invalid (sin nombre), 1 exact dup (phone), 1 new,
    # 1 possible dup (similar name + nearby, in-run).
    assert result["received"] == 4
    assert result["invalid"] == 1
    assert result["new"] == 2
    assert result["exact_duplicates"] == 1
    assert result["possible_duplicates"] == 1
    assert result["dry_run"] is True

    response = await client.get(f"{BASE}/restaurants", headers=auth_headers["admin"])
    assert response.json()["total"] == 1  # only the pre-existing restaurant


async def test_manual_import_loads_and_flags_possible_duplicate(client, auth_headers):
    await _create_existing_restaurant(client, auth_headers["admin"])

    result = await _run_ingestion(client, auth_headers["admin"], SAMPLE_CSV, dry_run=False)

    assert result["new"] == 2
    assert result["exact_duplicates"] == 1
    assert result["possible_duplicates"] == 1
    assert result["possible_duplicate_details"][0]["criterion"] == "similarity_proximity"

    # 1 pre-existing + 2 new restaurants (the exact dup merged, no new row).
    response = await client.get(f"{BASE}/restaurants", headers=auth_headers["admin"])
    body = response.json()
    assert body["total"] == 3
    assert all(r["lead"]["status"] == "new" for r in body["items"] if r["name"] != "Kebab Existente")

    # The review queue has exactly the possible duplicate.
    queue = await client.get(f"{BASE}/duplicates", headers=auth_headers["admin"])
    queue_body = queue.json()
    assert queue_body["total"] == 1
    assert queue_body["items"][0]["restaurant"]["name"] == "Kebab Nuvvo"
    assert queue_body["items"][0]["duplicate_of"]["name"] == "Kebab Nuevo"


async def test_second_ingestion_run_is_idempotent(client, auth_headers):
    await _create_existing_restaurant(client, auth_headers["admin"])
    await _run_ingestion(client, auth_headers["admin"], SAMPLE_CSV, dry_run=False)

    result = await _run_ingestion(client, auth_headers["admin"], SAMPLE_CSV, dry_run=False)

    # Everything matches by phone this time: no new, no possible duplicates.
    assert result["new"] == 0
    assert result["possible_duplicates"] == 0
    assert result["exact_duplicates"] == 3
    assert result["invalid"] == 1

    response = await client.get(f"{BASE}/restaurants", headers=auth_headers["admin"])
    assert response.json()["total"] == 3  # unchanged


async def test_resolve_keep_both(client, auth_headers):
    await _create_existing_restaurant(client, auth_headers["admin"])
    await _run_ingestion(client, auth_headers["admin"], SAMPLE_CSV, dry_run=False)

    queue = await client.get(f"{BASE}/duplicates", headers=auth_headers["admin"])
    suspect_id = queue.json()["items"][0]["restaurant"]["id"]

    response = await client.post(
        f"{BASE}/duplicates/{suspect_id}/resolve",
        json={"action": "keep_both"},
        headers=auth_headers["sales"],  # resolving is sales work too
    )
    assert response.status_code == 200

    queue = await client.get(f"{BASE}/duplicates", headers=auth_headers["admin"])
    assert queue.json()["total"] == 0

    listing = await client.get(f"{BASE}/restaurants", headers=auth_headers["admin"])
    assert listing.json()["total"] == 3  # both restaurants remain


async def test_resolve_merge(client, auth_headers):
    await _create_existing_restaurant(client, auth_headers["admin"])
    await _run_ingestion(client, auth_headers["admin"], SAMPLE_CSV, dry_run=False)

    queue = await client.get(f"{BASE}/duplicates", headers=auth_headers["admin"])
    suspect_id = queue.json()["items"][0]["restaurant"]["id"]

    response = await client.post(
        f"{BASE}/duplicates/{suspect_id}/resolve",
        json={"action": "merge"},
        headers=auth_headers["admin"],
    )
    assert response.status_code == 200

    listing = await client.get(f"{BASE}/restaurants", headers=auth_headers["admin"])
    assert listing.json()["total"] == 2  # suspect merged away

    names = {r["name"] for r in listing.json()["items"]}
    assert "Kebab Nuvvo" not in names
    merged_id = next(
        r["id"] for r in listing.json()["items"] if r["name"] == "Kebab Nuevo"
    )
    detail = await client.get(
        f"{BASE}/restaurants/{merged_id}", headers=auth_headers["admin"]
    )
    # The suspect's data filled the original's gaps (detail has the email).
    assert detail.json()["email"] == "hola@kebabnuevo.example"


async def test_resolve_unknown_duplicate_404(client, auth_headers):
    import uuid

    response = await client.post(
        f"{BASE}/duplicates/{uuid.uuid4()}/resolve",
        json={"action": "merge"},
        headers=auth_headers["admin"],
    )
    assert response.status_code == 404
