"""Lead scoring tests (plan FASE 6 / test_lead_scoring)."""

from __future__ import annotations

import json

import pytest

from app.models import DeliveryPresence, Lead, Restaurant
from app.models.enums import DeliveryPlatform, DetectionMethod
from app.services.normalization import normalize_name
from app.services.scoring import (
    Rule,
    ScoringConfigError,
    ScoringRules,
    compute_score,
    load_rules,
    score_restaurant,
)

BASE = "/api/v1"


def _rules(
    *,
    rules: list[Rule] | None = None,
    negative_rules: list[Rule] | None = None,
    service_cities: list[str] | None = None,
    target_categories: list[str] | None = None,
    max_score: int = 100,
) -> ScoringRules:
    return ScoringRules(
        version=1,
        max_score=max_score,
        service_cities=service_cities if service_cities is not None else ["madrid"],
        target_categories=target_categories if target_categories is not None else ["kebab"],
        rules=rules
        if rules is not None
        else [
            Rule("delivery_detected", "Delivery detectado", 25),
            Rule("in_service_area", "Zona cubierta", 20),
            Rule("has_phone", "Teléfono", 10),
            Rule("has_website", "Web", 5),
            Rule("has_email", "Email", 5),
            Rule("target_category", "Categoría objetivo", 10),
        ],
        negative_rules=negative_rules
        if negative_rules is not None
        else [
            Rule("possible_duplicate", "Posible duplicado", -15),
            Rule("no_contact_data", "Sin contacto", -20),
        ],
    )


def _restaurant(**kwargs) -> Restaurant:
    defaults = {"name": "Kebab Ficticio"}
    defaults.update(kwargs)
    defaults.setdefault("normalized_name", normalize_name(defaults["name"]))
    return Restaurant(**defaults)


# --- pure scoring ---


def test_full_positive_stack():
    restaurant = _restaurant(
        phone="+34611222333",
        website="ficticio.example",
        email="hola@ficticio.example",
        city="Madrid",
        category="kebab",
    )
    restaurant.delivery_presence = [
        DeliveryPresence(platform=DeliveryPlatform.GLOVO, detected=True,
                         detection_method=DetectionMethod.MANUAL)
    ]
    score, reasons = compute_score(restaurant, _rules())
    # 25 delivery + 20 zona + 10 teléfono + 5 web + 5 email + 10 categoría
    assert score == 75
    assert len(reasons) == 6
    assert reasons[0]["factor"] == "delivery_detected"
    assert reasons[0]["points"] == 25
    assert reasons[0]["label"] == "Delivery detectado"


def test_sparse_restaurant_scores_low():
    restaurant = _restaurant(phone="+34611222333", city="Barcelona", category="pizza")
    score, reasons = compute_score(restaurant, _rules())
    # solo teléfono (fuera de zona, sin delivery, categoría no objetivo)
    assert score == 10
    assert [r["factor"] for r in reasons] == ["has_phone"]


def test_disabled_rule_does_not_score():
    rules = _rules(
        rules=[
            Rule("delivery_detected", "Delivery", 25, enabled=False),
            Rule("has_phone", "Teléfono", 10),
        ]
    )
    restaurant = _restaurant(phone="+34611222333")
    restaurant.delivery_presence = [
        DeliveryPresence(platform=DeliveryPlatform.GLOVO, detected=True,
                         detection_method=DetectionMethod.MANUAL)
    ]
    score, reasons = compute_score(restaurant, rules)
    assert score == 10
    assert all(r["factor"] != "delivery_detected" for r in reasons)


def test_weights_are_editable_without_code_changes():
    """The core promise of FASE 6: change points in config, score changes."""
    light = _rules(rules=[Rule("has_phone", "Teléfono", 10)])
    heavy = _rules(rules=[Rule("has_phone", "Teléfono", 40)])
    restaurant = _restaurant(phone="+34611222333")
    assert compute_score(restaurant, light)[0] == 10
    assert compute_score(restaurant, heavy)[0] == 40


def test_negative_rule_for_possible_duplicate():
    restaurant = _restaurant(phone="+34611222333", possible_duplicate_of_id="00000000-0000-0000-0000-000000000001")
    score, reasons = compute_score(restaurant, _rules(rules=[Rule("has_phone", "Teléfono", 30)]))
    assert score == 15  # 30 - 15
    assert reasons[-1]["points"] == -15


def test_no_contact_data_clamps_to_zero():
    restaurant = _restaurant()  # no phone, no email, no website, no positives
    score, reasons = compute_score(restaurant, _rules(rules=[]))
    assert score == 0  # -20 clamped at 0
    assert [r["factor"] for r in reasons] == ["no_contact_data"]


def test_score_clamped_to_max():
    rules = _rules(
        rules=[
            Rule("has_phone", "Teléfono", 40),
            Rule("has_website", "Web", 40),
            Rule("has_email", "Email", 40),
        ]
    )
    restaurant = _restaurant(phone="+34611222333", website="x.example", email="x@x.example")
    assert compute_score(restaurant, rules)[0] == 100


def test_service_city_normalized_comparison():
    rules = _rules(
        service_cities=["Madrid"],
        rules=[Rule("in_service_area", "Zona", 20)],
        negative_rules=[],
    )
    assert compute_score(_restaurant(city="MADRID"), rules)[0] == 20
    assert compute_score(_restaurant(city="Alcobendás"), rules)[0] == 0


def test_category_normalized_comparison():
    rules = _rules(
        target_categories=["Kebab"],
        rules=[Rule("target_category", "Cat", 10)],
        negative_rules=[],
    )
    assert compute_score(_restaurant(category=" KEBAB "), rules)[0] == 10


# --- rules file loading ---


def test_load_rules_from_json(tmp_path):
    payload = {
        "version": 3,
        "max_score": 90,
        "service_cities": ["Madrid", "Getafe"],
        "target_categories": ["kebab"],
        "rules": [{"id": "has_phone", "label": "Teléfono", "points": 12}],
        "negative_rules": [
            {"id": "possible_duplicate", "label": "Dup", "points": -5, "enabled": False}
        ],
    }
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    rules = load_rules(path)
    assert rules.version == 3
    assert rules.max_score == 90
    assert rules.service_cities == ["madrid", "getafe"]  # normalized
    assert rules.rules[0].points == 12
    assert rules.negative_rules[0].enabled is False


def test_load_rules_missing_file_raises(tmp_path):
    with pytest.raises(ScoringConfigError):
        load_rules(tmp_path / "no-existe.json")


def test_load_rules_unknown_rule_raises(tmp_path):
    payload = {"version": 1, "rules": [{"id": "regla_inventada", "label": "X", "points": 5}]}
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ScoringConfigError, match="regla_inventada"):
        load_rules(path)


def test_default_rules_file_is_valid():
    """The repo's own scoring_rules.json must always load cleanly."""
    rules = load_rules()
    assert rules.version >= 1
    assert rules.max_score == 100
    assert len(rules.rules) >= 6


# --- persistence (service level) ---


async def test_score_restaurant_persists_score_and_reasons(db_session):
    restaurant = _restaurant(phone="+34611222333", city="Madrid", category="kebab")
    db_session.add(restaurant)
    await db_session.commit()

    lead = await score_restaurant(db_session, restaurant.id, rules=_rules())
    assert lead is not None
    assert lead.score is not None and lead.score > 0
    assert lead.score_reasons
    assert lead.scored_at is not None

    await db_session.commit()
    stored = await db_session.get(Lead, lead.id)
    assert stored.score == lead.score


async def test_score_restaurant_missing_returns_none(db_session):
    import uuid

    assert await score_restaurant(db_session, uuid.uuid4(), rules=_rules()) is None


# --- API ---


async def test_create_restaurant_is_scored_immediately(client, auth_headers):
    response = await client.post(
        f"{BASE}/restaurants",
        json={"name": "Kebab Puntuado", "phone": "+34611222333", "city": "Madrid",
              "category": "kebab"},
        headers=auth_headers["sales"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["lead"]["score"] is not None
    assert body["lead"]["score"] > 0
    assert body["lead"]["score_reasons"]


async def test_recalculate_endpoint_updates_score(client, auth_headers):
    created = await client.post(
        f"{BASE}/restaurants",
        json={"name": "Kebab Recalculado", "phone": "+34611222333", "city": "Madrid",
              "category": "kebab"},
        headers=auth_headers["sales"],
    )
    restaurant_id = created.json()["id"]
    first_score = created.json()["lead"]["score"]

    # Removing the phone must lower the score after recalculation.
    await client.patch(
        f"{BASE}/restaurants/{restaurant_id}",
        json={"phone": None},
        headers=auth_headers["sales"],
    )
    response = await client.post(
        f"{BASE}/restaurants/{restaurant_id}/score/recalculate",
        headers=auth_headers["sales"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["score"] < first_score
    assert body["score_reasons"]

    detail = await client.get(
        f"{BASE}/restaurants/{restaurant_id}", headers=auth_headers["sales"]
    )
    assert detail.json()["lead"]["score"] == body["score"]


async def test_recalculate_404(client, auth_headers):
    import uuid

    response = await client.post(
        f"{BASE}/restaurants/{uuid.uuid4()}/score/recalculate",
        headers=auth_headers["sales"],
    )
    assert response.status_code == 404


async def test_ingestion_scores_new_restaurants(client, auth_headers):
    csv_content = (
        "name,phone,website,city,category\n"
        "Kebab Con Puntos,+34611222333,conpuntos.example,Madrid,kebab\n"
    )
    response = await client.post(
        f"{BASE}/ingestion/run",
        json={
            "connector": "manual_import",
            "params": {"csv_content": csv_content},
            "dry_run": False,
        },
        headers=auth_headers["admin"],
    )
    assert response.status_code == 200, response.text
    listing = await client.get(f"{BASE}/restaurants", headers=auth_headers["admin"])
    item = next(
        r for r in listing.json()["items"] if r["name"] == "Kebab Con Puntos"
    )
    assert item["lead"]["score"] is not None
    assert item["lead"]["score"] > 0
