"""Normalization helpers (basic M2 version).

Full normalization (phones to E.164 via phonenumbers, address cleanup)
lands in M3 — this module is the single seam where it grows, so callers
never change.
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercase, strip accents and collapse whitespace."""
    lowered = name.strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return _WHITESPACE.sub(" ", without_accents).strip()
