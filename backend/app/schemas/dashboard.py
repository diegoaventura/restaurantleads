"""Dashboard KPIs (docs/API.md — GET /api/v1/dashboard/stats)."""

from __future__ import annotations

from pydantic import BaseModel


class DashboardStats(BaseModel):
    restaurants_total: int
    leads_total: int
    leads_new: int
    leads_qualified: int
    pending_contact: int  # new + qualified (not yet contacted)
    follow_ups_due_today: int
    follow_ups_overdue: int  # pending and already late
    interested: int
    meetings: int
    customers: int
    conversion_rate: float  # customers / leads_total (descriptive only)
