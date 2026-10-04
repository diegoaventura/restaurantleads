"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    dashboard,
    duplicates,
    follow_ups,
    health,
    ingestion,
    interactions,
    restaurants,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(restaurants.router, prefix="/restaurants", tags=["restaurants", "leads"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(duplicates.router, prefix="/duplicates", tags=["duplicates"])
api_router.include_router(interactions.router, tags=["interactions"])
api_router.include_router(follow_ups.router, tags=["follow-ups"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
