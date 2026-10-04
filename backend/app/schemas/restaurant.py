"""Restaurant and lead schemas (request/response)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ContactType,
    DeliveryPlatform,
    DetectionMethod,
    FollowUpStatus,
    InteractionChannel,
    InteractionResult,
    LeadPriority,
    LeadStatus,
    SourceType,
)


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    website: str | None = Field(default=None, max_length=254)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=12)
    category: str | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class RestaurantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    website: str | None = Field(default=None, max_length=254)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=12)
    category: str | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: LeadStatus
    priority: LeadPriority
    score: int | None
    score_reasons: list[dict[str, Any]] | None
    scored_at: datetime | None
    assigned_to: UUID | None
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
    priority: LeadPriority | None = None
    assigned_to: UUID | None = None


class RestaurantSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: SourceType
    source_url: str | None
    external_id: str | None
    first_seen_at: datetime
    last_seen_at: datetime


class DeliveryPresenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: DeliveryPlatform
    detected: bool
    url: str | None
    detection_method: DetectionMethod
    first_detected_at: datetime
    last_detected_at: datetime


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_type: ContactType
    value: str
    source: SourceType
    verified: bool
    verified_at: datetime | None
    created_at: datetime


class InteractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel: InteractionChannel
    occurred_at: datetime
    result: InteractionResult
    notes: str | None
    created_by: UUID | None
    created_at: datetime


class FollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scheduled_at: datetime
    channel: InteractionChannel
    status: FollowUpStatus
    notes: str | None
    completed_at: datetime | None
    created_by: UUID | None
    created_at: datetime


class RestaurantOut(BaseModel):
    """Row shape for the leads list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str | None
    website: str | None
    city: str | None
    category: str | None
    lead: LeadOut | None
    delivery_platforms: list[str]  # model property (eager-loaded relations)
    last_interaction_at: datetime | None
    next_follow_up_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RestaurantDetail(RestaurantOut):
    """Full profile (docs/API.md — ficha del restaurante)."""

    email: str | None
    address: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    phone_source: SourceType | None
    phone_verified_at: datetime | None
    email_source: SourceType | None
    email_verified_at: datetime | None
    website_source: SourceType | None
    website_verified_at: datetime | None
    sources: list[RestaurantSourceOut]
    delivery_presence: list[DeliveryPresenceOut]
    contacts: list[ContactOut]
    interactions: list[InteractionOut]
    follow_ups: list[FollowUpOut]


class RestaurantExport(BaseModel):
    """GDPR portability: the complete record of one restaurant."""

    exported_at: datetime
    restaurant: RestaurantDetail
