"""OSM connector unit tests — pure parsing, no network calls."""

from __future__ import annotations

import pytest

from app.ingestion.base import IngestionError
from app.ingestion.connectors.osm import _parse_bbox, element_to_candidate
from app.models.enums import SourceType


def _node(tags: dict) -> dict:
    return {
        "type": "node",
        "id": 9876543,
        "lat": 40.416775,
        "lon": -3.703790,
        "tags": tags,
    }


def test_node_with_full_tags():
    candidate = element_to_candidate(
        _node(
            {
                "name": "Kebab Hassan",
                "phone": "+34 612 34 56 78",
                "contact:phone": "+34 612 34 56 79",  # ignored, first key wins
                "website": "https://kebabhassan.example",
                "addr:street": "Calle Ficticia",
                "addr:housenumber": "5",
                "addr:city": "Madrid",
                "addr:postcode": "28012",
                "cuisine": "kebab;pizza",
            }
        )
    )
    assert candidate is not None
    assert candidate.name == "Kebab Hassan"
    assert candidate.phone == "+34 612 34 56 78"
    assert candidate.website == "https://kebabhassan.example"
    assert candidate.address == "Calle Ficticia 5"
    assert candidate.city == "Madrid"
    assert candidate.postal_code == "28012"
    assert candidate.category == "kebab"  # first cuisine value only
    assert candidate.latitude == 40.416775
    assert candidate.source == SourceType.OSM
    assert candidate.external_id == "node/9876543"
    assert candidate.source_url == "https://www.openstreetmap.org/node/9876543"


def test_way_without_name_is_skipped():
    element = {"type": "way", "id": 1, "center": {"lat": 1.0, "lon": 2.0}, "tags": {}}
    assert element_to_candidate(element) is None


def test_way_uses_center_coordinates():
    element = {
        "type": "way",
        "id": 2222,
        "center": {"lat": 41.3874, "lon": 2.1686},
        "tags": {"name": "Sushi Kaizen", "phone": "+34931234567"},
    }
    candidate = element_to_candidate(element)
    assert candidate is not None
    assert candidate.latitude == 41.3874
    assert candidate.longitude == 2.1686
    assert candidate.external_id == "way/2222"


def test_multi_valued_phone_takes_first():
    candidate = element_to_candidate(
        _node({"name": "Multi Phone", "phone": "+346111111111;+346111111112"})
    )
    assert candidate is not None
    assert candidate.phone == "+346111111111"


def test_bbox_valid():
    assert _parse_bbox("40.30,-3.90,40.60,-3.60") == (40.30, -3.90, 40.60, -3.60)


def test_bbox_wrong_count_raises():
    with pytest.raises(IngestionError):
        _parse_bbox("40.30,-3.90")


def test_bbox_non_numeric_raises():
    with pytest.raises(IngestionError):
        _parse_bbox("norte,oeste,sur,este")


def test_bbox_out_of_range_raises():
    with pytest.raises(IngestionError):
        _parse_bbox("-95.0,-3.90,40.60,-3.60")
