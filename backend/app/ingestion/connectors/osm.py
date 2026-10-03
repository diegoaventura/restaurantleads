"""OpenStreetMap connector via the public Overpass API.

Free, legal and official (unlike scraping delivery platforms, which their
ToS forbid). Uses `amenity=restaurant` with a bounding box; requests are
rate-limited (configurable interval) and have an explicit timeout.

The element→candidate mapping is a pure function so it can be tested
without touching the network.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from app.core.config import get_settings
from app.ingestion.base import IngestionError
from app.models.enums import SourceType
from app.schemas.ingestion import RestaurantCandidate

_last_request_at = 0.0  # module-level guard for the minimum interval


def _overpass_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    timeout = int(get_settings().overpass_timeout_seconds)
    return (
        f"[out:json][timeout:{timeout}];"
        f'nwr["amenity"="restaurant"]({south},{west},{north},{east});'
        "out center tags;"
    )


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    try:
        parts = [float(p.strip()) for p in raw.split(",")]
    except ValueError as exc:
        raise IngestionError(
            "params.bbox inválido: usar 'south,west,north,east' (4 números)"
        ) from exc
    if len(parts) != 4:
        raise IngestionError(
            "params.bbox inválido: usar 'south,west,north,east' (4 números)"
        )
    south, west, north, east = parts
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise IngestionError("params.bbox fuera de rango o desordenado")
    return south, west, north, east


def _first_tag(tags: dict, *keys: str) -> str | None:
    for key in keys:
        value = tags.get(key)
        if value:
            # OSM lists multiple values separated by ';': take the first.
            first = value.split(";")[0].strip()
            if first:
                return first
    return None


def element_to_candidate(element: dict) -> RestaurantCandidate | None:
    """Map one Overpass element to a candidate; None if unusable."""
    tags: dict = element.get("tags") or {}
    name = tags.get("name", "").strip() or None
    if name is None:
        return None  # unnamed POIs are not contactable leads

    center: dict = element.get("center") or {}
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))

    street = _first_tag(tags, "addr:street")
    housenumber = _first_tag(tags, "addr:housenumber")
    address = f"{street} {housenumber}".strip() if street or housenumber else None

    element_type = element.get("type", "")
    element_id = element.get("id")

    return RestaurantCandidate(
        name=name,
        phone=_first_tag(tags, "phone", "contact:phone"),
        email=_first_tag(tags, "email", "contact:email"),
        website=_first_tag(tags, "website", "contact:website", "url"),
        address=address,
        city=_first_tag(tags, "addr:city"),
        postal_code=_first_tag(tags, "addr:postcode"),
        category=_first_tag(tags, "cuisine"),
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        source=SourceType.OSM,
        source_url=(
            f"https://www.openstreetmap.org/{element_type}/{element_id}"
            if element_id is not None
            else None
        ),
        external_id=(
            f"{element_type}/{element_id}" if element_id is not None else None
        ),
    )


class OSMConnector:
    name = "osm"

    def __init__(self, bbox: str) -> None:
        self._bbox = _parse_bbox(bbox)

    async def fetch(self) -> list[RestaurantCandidate]:
        global _last_request_at
        settings = get_settings()

        # Respect the minimum interval between Overpass requests.
        elapsed = time.monotonic() - _last_request_at
        wait = settings.overpass_request_interval_seconds - elapsed
        if wait > 0:
            await asyncio.sleep(wait)

        try:
            async with httpx.AsyncClient(
                timeout=settings.overpass_timeout_seconds
            ) as client:
                response = await client.post(
                    settings.overpass_url,
                    data={"data": _overpass_query(self._bbox)},
                )
        except httpx.HTTPError as exc:
            raise IngestionError(f"Overpass no accesible: {exc}") from exc
        finally:
            _last_request_at = time.monotonic()

        if response.status_code != 200:
            raise IngestionError(
                f"Overpass respondió {response.status_code}; "
                "revisa el bbox o inténtalo más tarde"
            )

        elements = response.json().get("elements", [])
        candidates = []
        for element in elements:
            candidate = element_to_candidate(element)
            if candidate is not None:
                candidates.append(candidate)
        return candidates
