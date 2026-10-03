"""Ingestion schemas: the normalized candidate and the run request/result.

`RestaurantCandidate` is the single interface between every connector and
the pipeline — a connector never talks to the database directly.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import SourceType


class RestaurantCandidate(BaseModel):
    """Normalized output of every connector (docs/ARCHITECTURE.md)."""

    name: str | None = None
    phone: str | None = None  # raw at connector level, E.164 after normalization
    email: str | None = None
    website: str | None = None
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    category: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    source: SourceType
    source_url: str | None = None
    external_id: str | None = None


class IngestionRunRequest(BaseModel):
    connector: str
    params: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False  # never writes to the database


class PossibleDuplicateDetail(BaseModel):
    restaurant_id: UUID
    name: str | None
    duplicate_of_id: UUID
    duplicate_of_name: str | None
    criterion: str


class IngestionRunResult(BaseModel):
    run_id: UUID
    connector: str
    dry_run: bool
    received: int
    valid: int
    new: int
    exact_duplicates: int
    possible_duplicates: int
    invalid: int
    invalid_reasons: list[str]  # capped, first N reasons
    possible_duplicate_details: list[PossibleDuplicateDetail]
