"""Manual CSV import connector.

Columns (all optional except `name` — validated by the pipeline):
    name, phone, email, website, address, city, postal_code, category,
    latitude, longitude, external_id

The connector only parses; normalization/validation/dedup happen in the
pipeline. This is the zero-cost ingestion path for M3.
"""

from __future__ import annotations

import csv
import io

from app.ingestion.base import IngestionError
from app.models.enums import SourceType
from app.schemas.ingestion import RestaurantCandidate

CSV_COLUMNS = (
    "name",
    "phone",
    "email",
    "website",
    "address",
    "city",
    "postal_code",
    "category",
    "latitude",
    "longitude",
    "external_id",
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _to_float(value: str | None) -> float | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


class ManualImportConnector:
    name = "manual_import"

    def __init__(self, csv_content: str) -> None:
        if not csv_content or not csv_content.strip():
            raise IngestionError("params.csv_content es obligatorio y está vacío")
        self._csv_content = csv_content

    async def fetch(self) -> list[RestaurantCandidate]:
        reader = csv.DictReader(io.StringIO(self._csv_content))
        candidates: list[RestaurantCandidate] = []
        for row in reader:
            values = {k: _clean(v) for k, v in row.items() if k in CSV_COLUMNS}
            if not any(values.values()):
                continue  # fully empty line, skip silently
            if not values.get("name"):
                # Keep the row so the pipeline counts it as invalid
                # (a restaurant without a name cannot be contacted).
                candidates.append(
                    RestaurantCandidate(source=SourceType.MANUAL_IMPORT)
                )
                continue
            candidates.append(
                RestaurantCandidate(
                    name=values.get("name"),
                    phone=values.get("phone"),
                    email=values.get("email"),
                    website=values.get("website"),
                    address=values.get("address"),
                    city=values.get("city"),
                    postal_code=values.get("postal_code"),
                    category=values.get("category"),
                    latitude=_to_float(values.get("latitude")),
                    longitude=_to_float(values.get("longitude")),
                    source=SourceType.MANUAL_IMPORT,
                    external_id=values.get("external_id"),
                )
            )
        return candidates
