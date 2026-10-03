"""Normalization: names/texts, phones (E.164 via phonenumbers), websites.

Single seam for all data cleaning — ingestion (M3) and enrichment (M5)
share these functions so a value is normalized identically everywhere.
"""

from __future__ import annotations

import re
import unicodedata

import phonenumbers

from app.schemas.ingestion import RestaurantCandidate

_WHITESPACE = re.compile(r"\s+")
_PHONE_CLEANUP = re.compile(r"[^+0-9]")

DEFAULT_PHONE_REGION = "ES"


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_name(name: str) -> str:
    """Lowercase, strip accents and collapse whitespace (matching key)."""
    return _WHITESPACE.sub(" ", strip_accents(name.strip().lower())).strip()


def normalize_text(value: str | None) -> str | None:
    """normalize_name for optional fields (addresses, cities...)."""
    if not value:
        return None
    return normalize_name(value)


def normalize_phone(
    raw: str | None, region: str = DEFAULT_PHONE_REGION
) -> str | None:
    """Return the number in E.164 (+34612345678), or None if invalid."""
    if not raw:
        return None
    cleaned = _PHONE_CLEANUP.sub("", raw)
    if not cleaned:
        return None
    try:
        parsed = phonenumbers.parse(cleaned, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(
        parsed, phonenumbers.PhoneNumberFormat.E164
    )


def normalize_website(raw: str | None) -> str | None:
    """Return the root domain in lowercase ('kebabhassan.es'), or None."""
    if not raw:
        return None
    value = raw.strip().lower().rstrip("/")
    if "://" in value:
        value = value.split("://", 1)[1]
    value = value.split("/", 1)[0]
    if value.startswith("www."):
        value = value[4:]
    if not value or "." not in value:
        return None
    return value


def normalize_candidate(
    candidate: RestaurantCandidate,
) -> tuple[RestaurantCandidate, list[str]]:
    """Clean every field; returns the candidate plus parsing errors."""
    errors: list[str] = []
    phone = normalize_phone(candidate.phone)
    if candidate.phone and phone is None:
        errors.append(f"teléfono no válido: {candidate.phone!r}")

    name = candidate.name.strip() if candidate.name else None

    normalized = candidate.model_copy(
        update={
            "name": name or None,
            "phone": phone,
            "email": candidate.email.strip().lower() if candidate.email else None,
            "website": normalize_website(candidate.website),
            "address": candidate.address.strip() if candidate.address else None,
            "city": candidate.city.strip() if candidate.city else None,
            "postal_code": candidate.postal_code.strip()
            if candidate.postal_code
            else None,
            "category": candidate.category.strip().lower()
            if candidate.category
            else None,
        }
    )
    return normalized, errors


def validate_candidate(candidate: RestaurantCandidate) -> list[str]:
    """A lead must have a name and at least one contact channel."""
    reasons: list[str] = []
    if not candidate.name:
        reasons.append("sin nombre")
    if not (candidate.phone or candidate.email or candidate.website):
        reasons.append("sin datos de contacto (teléfono, email o web)")
    return reasons
