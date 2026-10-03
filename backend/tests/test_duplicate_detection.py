"""Tests for duplicate detection (plan FASE 4 matching priority)."""

from __future__ import annotations

from app.models import Restaurant, RestaurantSource
from app.models.enums import SourceType
from app.schemas.ingestion import RestaurantCandidate
from app.services import dedup
from app.services.dedup import MatchType
from app.services.normalization import normalize_name


async def _add_restaurant(db_session, name: str, **kwargs) -> Restaurant:
    restaurant = Restaurant(name=name, normalized_name=normalize_name(name), **kwargs)
    db_session.add(restaurant)
    await db_session.commit()
    return restaurant


def _candidate(**kwargs) -> RestaurantCandidate:
    defaults = {
        "name": "Restaurante Ficticio",
        "website": "ficticio.example",
        "source": SourceType.OSM,
    }
    defaults.update(kwargs)
    return RestaurantCandidate(**defaults)


async def test_match_by_external_id(db_session):
    restaurant = await _add_restaurant(db_session, "Ext Uno")
    db_session.add(
        RestaurantSource(
            restaurant_id=restaurant.id, source=SourceType.OSM, external_id="node/42"
        )
    )
    await db_session.commit()

    match = await dedup.find_match(
        db_session, _candidate(name="Ext Renombrado", external_id="node/42")
    )
    assert match.type is MatchType.EXACT
    assert match.criterion == "external_id"
    assert match.restaurant.id == restaurant.id


async def test_match_by_phone(db_session):
    restaurant = await _add_restaurant(db_session, "Telefono Uno", phone="+34611222333")

    match = await dedup.find_match(db_session, _candidate(phone="+34611222333"))
    assert match.type is MatchType.EXACT
    assert match.criterion == "phone"
    assert match.restaurant.id == restaurant.id


async def test_match_by_website_domain(db_session):
    restaurant = await _add_restaurant(db_session, "Web Uno", website="kebabuno.example")

    match = await dedup.find_match(
        db_session,
        _candidate(
            name="Kebab Uno Renovado",
            website="https://www.kebabuno.example/cart",
        ),
    )
    assert match.type is MatchType.EXACT
    assert match.criterion == "website"


async def test_match_by_name_and_address(db_session):
    restaurant = await _add_restaurant(
        db_session, "Kebab Dirección", address="Calle Ficticia 5"
    )

    match = await dedup.find_match(
        db_session,
        _candidate(
            name="Kebab Dirección",
            address="  CALLE   ficticia  5 ",
            website=None,
        ),
    )
    assert match.type is MatchType.EXACT
    assert match.criterion == "name_address"


async def test_possible_match_similarity_and_proximity(db_session):
    await _add_restaurant(
        db_session,
        "Kebab Nuevo",
        city="Alcobendas",
        latitude=40.547000,
        longitude=-3.635000,
    )

    match = await dedup.find_match(
        db_session,
        _candidate(
            name="Kebab Nuvvo",
            website=None,
            city="Alcobendas",
            latitude=40.547050,
            longitude=-3.634950,
        ),
    )
    assert match.type is MatchType.POSSIBLE
    assert match.criterion == "similarity_proximity"


async def test_same_name_far_away_is_not_a_duplicate(db_session):
    await _add_restaurant(
        db_session,
        "Kebab Nuevo",
        city="Alcobendas",
        latitude=40.547000,
        longitude=-3.635000,
    )

    match = await dedup.find_match(
        db_session,
        _candidate(
            name="Kebab Nuevo",
            website=None,
            city="Barcelona",
            latitude=41.387400,
            longitude=2.168600,
        ),
    )
    assert match.type is MatchType.NONE


async def test_same_name_without_coordinates_is_not_a_duplicate(db_session):
    """Repeated names may be franchises — without proximity, stay conservative."""
    await _add_restaurant(db_session, "Sushi Kaizen", city="Madrid")

    match = await dedup.find_match(
        db_session, _candidate(name="Sushi Kaizen", website=None, city="Madrid")
    )
    assert match.type is MatchType.NONE


async def test_resolve_keep_both(db_session):
    original = await _add_restaurant(db_session, "Original Uno", website="uno.example")
    suspect = await _add_restaurant(
        db_session, "Original Dos", possible_duplicate_of_id=original.id
    )

    await dedup.resolve_duplicate(db_session, suspect, action="keep_both")
    await db_session.commit()
    await db_session.refresh(suspect)

    assert suspect.possible_duplicate_of_id is None
    assert (await db_session.get(Restaurant, suspect.id)) is not None  # still there


async def test_resolve_merge_fills_fields_and_deletes_suspect(db_session):
    original = await _add_restaurant(db_session, "Original Uno", phone="+346000000001")
    suspect = await _add_restaurant(
        db_session,
        "Original Uno Dos",
        email="hola@ficticio.example",
        city="Alcobendas",
        possible_duplicate_of_id=original.id,
    )

    await dedup.resolve_duplicate(db_session, suspect, action="merge")
    await db_session.commit()

    refreshed = await db_session.get(Restaurant, original.id)
    assert refreshed is not None
    assert refreshed.email == "hola@ficticio.example"  # filled, not overwritten
    assert refreshed.city == "Alcobendas"
    assert refreshed.phone == "+346000000001"  # existing data kept
    assert (await db_session.get(Restaurant, suspect.id)) is None  # merged away
