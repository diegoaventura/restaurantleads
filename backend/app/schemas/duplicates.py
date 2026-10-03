"""Duplicate review queue schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.restaurant import RestaurantOut


class DuplicateItem(BaseModel):
    restaurant: RestaurantOut
    duplicate_of: RestaurantOut


class ResolveRequest(BaseModel):
    action: Literal["merge", "keep_both"]
