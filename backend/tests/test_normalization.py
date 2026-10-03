"""Unit tests for normalization (phones E.164, names, websites)."""

from __future__ import annotations

from app.services.normalization import (
    normalize_name,
    normalize_phone,
    normalize_website,
)


# --- normalize_phone ---


def test_phone_spaced_spanish_mobile():
    assert normalize_phone("+34 612 34 56 78") == "+34612345678"


def test_phone_naked_national_number():
    assert normalize_phone("612345678") == "+34612345678"


def test_phone_naked_landline():
    assert normalize_phone("912345678") == "+34912345678"


def test_phone_parentheses_and_dashes():
    assert normalize_phone("(+34) 913-45-67-89") == "+34913456789"


def test_phone_international_valid_number_kept():
    assert normalize_phone("+44 20 7946 0018") == "+442079460018"


def test_phone_too_short_invalid_returns_none():
    assert normalize_phone("12345") is None


def test_phone_letters_returns_none():
    assert normalize_phone("no-es-un-telefono") is None


def test_phone_empty_and_none():
    assert normalize_phone(None) is None
    assert normalize_phone("") is None


# --- normalize_name ---


def test_name_strips_accents_case_and_whitespace():
    assert normalize_name("  Pizzería   NÁPOLI Vera ") == "pizzeria napoli vera"


def test_name_keeps_digits():
    assert normalize_name("Kebab 24 Horas") == "kebab 24 horas"


# --- normalize_website ---


def test_website_full_url_with_www_and_path():
    assert normalize_website("https://www.KebabHassan.es/pedir") == "kebabhassan.es"


def test_website_bare_domain():
    assert normalize_website("pizzerianapolivera.example") == "pizzerianapolivera.example"


def test_website_www_prefix():
    assert normalize_website("www.sushikaizen.example") == "sushikaizen.example"


def test_website_no_dot_returns_none():
    assert normalize_website("sin-punto") is None


def test_website_empty_and_none():
    assert normalize_website(None) is None
    assert normalize_website("") is None
