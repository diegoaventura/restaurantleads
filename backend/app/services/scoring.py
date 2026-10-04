"""Configurable, explainable lead scoring (plan FASE 6).

Weights live in `scoring_rules.json` (path configurable via env): changing
a score NEVER requires a code change — edit the file and recalculate. The
JSON controls which rules exist, their points and whether they are
enabled, plus the value lists (service cities, target categories).

Predicates are typed code (safe, testable, no expression evaluation).
Every score is explainable: `score_reasons` stores the matched factors
with their points — a score is never a black-box number.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.base import utcnow
from app.models import Lead, Restaurant
from app.services.normalization import normalize_name

logger = logging.getLogger("app")


class ScoringConfigError(Exception):
    """The rules file is missing, malformed or references an unknown rule."""


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    points: int
    enabled: bool = True


@dataclass(frozen=True)
class ScoringRules:
    version: int
    max_score: int = 100
    service_cities: list[str] = field(default_factory=list)
    target_categories: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    negative_rules: list[Rule] = field(default_factory=list)


# Predicates: rule id -> (does this rule apply to this restaurant?)
# Value lists (cities/categories) are normalized on BOTH sides so the
# comparison works whether rules were built by load_rules or by hand.
def _in_normalized(value: str | None, targets: list[str]) -> bool:
    if not value or not targets:
        return False
    return normalize_name(value) in {normalize_name(t) for t in targets}


_PREDICATES: dict[str, Callable[[Restaurant, "ScoringRules"], bool]] = {
    "delivery_detected": lambda r, _rules: any(
        p.detected for p in r.delivery_presence
    ),
    "in_service_area": lambda r, rules: _in_normalized(r.city, rules.service_cities),
    "has_phone": lambda r, _rules: bool(r.phone),
    "has_website": lambda r, _rules: bool(r.website),
    "has_email": lambda r, _rules: bool(r.email),
    "target_category": lambda r, rules: _in_normalized(
        r.category, rules.target_categories
    ),
    "possible_duplicate": lambda r, _rules: r.possible_duplicate_of_id is not None,
    "no_contact_data": lambda r, _rules: not (r.phone or r.email or r.website),
}


def load_rules(path: str | Path | None = None) -> ScoringRules:
    """Load and validate the rules file (JSON)."""
    rules_path = Path(path) if path is not None else Path(get_settings().scoring_rules_path)
    try:
        data = json.loads(rules_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScoringConfigError(
            f"No se encuentra el fichero de reglas: {rules_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ScoringConfigError(f"scoring_rules no es JSON válido: {exc}") from exc

    try:
        rules = ScoringRules(
            version=int(data["version"]),
            max_score=int(data.get("max_score", 100)),
            service_cities=[normalize_name(c) for c in data.get("service_cities", [])],
            target_categories=[
                normalize_name(c) for c in data.get("target_categories", [])
            ],
            rules=[Rule(**r) for r in data.get("rules", [])],
            negative_rules=[Rule(**r) for r in data.get("negative_rules", [])],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ScoringConfigError(f"scoring_rules malformado: {exc}") from exc

    # Fail fast on unknown rule ids (typos in the config must be loud).
    for rule in [*rules.rules, *rules.negative_rules]:
        if rule.id not in _PREDICATES:
            raise ScoringConfigError(f"Regla desconocida en scoring_rules: {rule.id!r}")
    return rules


def compute_score(
    restaurant: Restaurant, rules: ScoringRules
) -> tuple[int, list[dict]]:
    """Pure scoring: returns (score, reasons). Clamped to 0..max_score."""
    reasons: list[dict] = []
    total = 0
    for rule in [*rules.rules, *rules.negative_rules]:
        if not rule.enabled:
            continue
        if _PREDICATES[rule.id](restaurant, rules):
            total += rule.points
            reasons.append(
                {"factor": rule.id, "label": rule.label, "points": rule.points}
            )
    score = max(0, min(total, rules.max_score))
    return score, reasons


async def score_restaurant(
    db: AsyncSession, restaurant_id: UUID, *, rules: ScoringRules | None = None
) -> Lead | None:
    """Score one restaurant and persist score+reasons on its lead.

    Does NOT commit — the caller owns the transaction. Returns None when
    the restaurant does not exist (soft-deleted included).
    """
    rules = rules or load_rules()
    stmt = (
        select(Restaurant)
        .where(Restaurant.id == restaurant_id, Restaurant.deleted_at.is_(None))
        .options(
            selectinload(Restaurant.delivery_presence),
            selectinload(Restaurant.lead),
        )
    )
    restaurant = (await db.scalars(stmt)).first()
    if restaurant is None:
        return None

    score, reasons = compute_score(restaurant, rules)

    lead = restaurant.lead
    if lead is None:  # restaurants created outside the API/ingestion
        # Bare constructor + PARENT-side assignment: the relationship
        # kwarg (Lead(restaurant=...)) bypasses the save-update cascade.
        lead = Lead()
        restaurant.lead = lead
    lead.score = score
    lead.score_reasons = reasons
    lead.scored_at = utcnow()
    logger.debug("Scored %s -> %s (%s factors)", restaurant.name, score, len(reasons))
    return lead
