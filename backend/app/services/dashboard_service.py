"""Dashboard KPIs — descriptive counts only (no causal claims, plan FASE 13)."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FollowUp, Lead, Restaurant
from app.models.enums import FollowUpStatus, LeadStatus
from app.schemas.dashboard import DashboardStats

# Status groups shown in the dashboard.
PENDING_CONTACT_STATUSES = (LeadStatus.NEW, LeadStatus.QUALIFIED)


def _today_bounds() -> tuple[datetime, datetime]:
    start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def get_stats(db: AsyncSession) -> DashboardStats:
    today_start, today_end = _today_bounds()
    not_deleted = Restaurant.deleted_at.is_(None)

    # Leads grouped by status (only non-deleted restaurants).
    rows = await db.execute(
        select(Lead.status, func.count())
        .join(Restaurant, Lead.restaurant_id == Restaurant.id)
        .where(not_deleted)
        .group_by(Lead.status)
    )
    by_status = {status: count for status, count in rows.all()}
    leads_total = sum(by_status.values())

    restaurants_total = (
        await db.scalars(select(func.count()).select_from(Restaurant).where(not_deleted))
    ).one()

    follow_up_base = (
        select(func.count())
        .select_from(FollowUp)
        .join(Restaurant, FollowUp.restaurant_id == Restaurant.id)
        .where(not_deleted, FollowUp.status == FollowUpStatus.PENDING)
    )
    due_today = (
        await db.scalars(
            follow_up_base.where(
                FollowUp.scheduled_at >= today_start, FollowUp.scheduled_at < today_end
            )
        )
    ).one()
    overdue = (
        await db.scalars(
            follow_up_base.where(FollowUp.scheduled_at < today_start)
        )
    ).one()

    customers = by_status.get(LeadStatus.CUSTOMER, 0)
    return DashboardStats(
        restaurants_total=restaurants_total,
        leads_total=leads_total,
        leads_new=by_status.get(LeadStatus.NEW, 0),
        leads_qualified=by_status.get(LeadStatus.QUALIFIED, 0),
        pending_contact=sum(by_status.get(s, 0) for s in PENDING_CONTACT_STATUSES),
        follow_ups_due_today=due_today,
        follow_ups_overdue=overdue,
        interested=by_status.get(LeadStatus.INTERESTED, 0),
        meetings=by_status.get(LeadStatus.MEETING, 0),
        customers=customers,
        conversion_rate=round(customers / leads_total, 4) if leads_total else 0.0,
    )
