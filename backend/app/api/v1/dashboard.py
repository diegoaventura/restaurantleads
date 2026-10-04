"""Dashboard endpoint (plan FASE 8): KPIs for the main screen."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import User
from app.schemas.dashboard import DashboardStats
from app.services import dashboard_service

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def stats(
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(get_current_user),
) -> DashboardStats:
    return await dashboard_service.get_stats(db)
