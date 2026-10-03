"""Connector interface and shared ingestion errors.

A connector extracts candidates from one source and NEVER touches the
database — normalization, validation, deduplication and loading are the
pipeline's job. Compliance: only public/official sources are allowed (see
docs/ARCHITECTURE.md — no scraping of delivery platforms, no ToS bypass).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.ingestion import RestaurantCandidate


class IngestionError(Exception):
    """A connector could not be built or its source failed."""


@runtime_checkable
class Connector(Protocol):
    """Every connector returns a list of (raw) RestaurantCandidates."""

    name: str

    async def fetch(self) -> list[RestaurantCandidate]: ...
