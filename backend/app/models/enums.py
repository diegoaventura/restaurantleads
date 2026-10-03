"""Domain enumerations.

Values are lowercase and stored in native PostgreSQL enum types (one DB enum
per Python enum — see docs/DATABASE.md). Adding a value requires an Alembic
migration: native enums cannot be altered with a simple INSERT.

`pg_enum` builds an Enum column that persists the *values* (not the member
names) and is reused by every model to avoid duplicated definitions.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum


def pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    """SQLAlchemy Enum storing StrEnum values in a native PG enum type."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
    )


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    SALES = "sales"


class LeadStatus(enum.StrEnum):
    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    NO_RESPONSE = "no_response"
    FOLLOW_UP = "follow_up"
    INTERESTED = "interested"
    MEETING = "meeting"
    CUSTOMER = "customer"
    NOT_INTERESTED = "not_interested"
    WRONG_NUMBER = "wrong_number"
    OUT_OF_AREA = "out_of_area"
    DUPLICATE = "duplicate"


class LeadPriority(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceType(enum.StrEnum):
    MANUAL_IMPORT = "manual_import"
    OSM = "osm"
    GOOGLE_PLACES = "google_places"
    MANUAL = "manual"


class DeliveryPlatform(enum.StrEnum):
    GLOVO = "glovo"
    UBER_EATS = "uber_eats"
    JUST_EAT = "just_eat"
    DELIVEROO = "deliveroo"
    OWN_DELIVERY = "own_delivery"
    OTHER = "other"


class DetectionMethod(enum.StrEnum):
    WEBSITE_LINK = "website_link"
    MANUAL = "manual"
    API = "api"


class ContactType(enum.StrEnum):
    PHONE = "phone"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    ADDRESS = "address"


class InteractionChannel(enum.StrEnum):
    CALL = "call"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    MEETING = "meeting"
    OTHER = "other"


class InteractionResult(enum.StrEnum):
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CALLBACK_REQUESTED = "callback_requested"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    MEETING_SCHEDULED = "meeting_scheduled"
    WRONG_NUMBER = "wrong_number"
    OUT_OF_AREA = "out_of_area"
    DUPLICATE_REPORTED = "duplicate_reported"


class FollowUpStatus(enum.StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class GenerationType(enum.StrEnum):
    BRIEFING = "briefing"
    CALL_SCRIPT = "call_script"
    COMMERCIAL_MESSAGE = "commercial_message"
    FOLLOW_UP_MESSAGE = "follow_up_message"
