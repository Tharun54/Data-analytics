"""SaaS plan catalogue and limit enforcement."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, func, select

from .models import Dashboard, Organization, UsageEvent

PLANS: dict[str, dict] = {
    "free": {
        "name": "Free", "price_usd": 0,
        "analyses_per_month": 5, "datasets_per_month": 3, "dashboards": 2,
        "web_research": False, "sharing": False,
    },
    "pro": {
        "name": "Pro", "price_usd": 49,
        "analyses_per_month": 100, "datasets_per_month": 50, "dashboards": 25,
        "web_research": True, "sharing": True,
    },
    "business": {
        "name": "Business", "price_usd": 299,
        "analyses_per_month": 1000, "datasets_per_month": 500, "dashboards": None,
        "web_research": True, "sharing": True,
    },
}


def plan_for(org: Organization) -> dict:
    return PLANS.get(org.plan, PLANS["free"])


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def usage_this_month(session: Session, org_id: int, kind: str) -> int:
    stmt = select(func.count()).select_from(UsageEvent).where(
        UsageEvent.org_id == org_id, UsageEvent.kind == kind,
        UsageEvent.created_at >= _month_start(),
    )
    return session.exec(stmt).one()


def enforce_and_record(session: Session, org: Organization, kind: str) -> None:
    limit = plan_for(org)[{"analysis": "analyses_per_month", "dataset": "datasets_per_month"}[kind]]
    used = usage_this_month(session, org.id, kind)
    if limit is not None and used >= limit:
        raise HTTPException(402, f"Monthly {kind} limit reached for the {plan_for(org)['name']} plan ({limit}). Upgrade to continue.")
    session.add(UsageEvent(org_id=org.id, kind=kind))


def enforce_dashboard_limit(session: Session, org: Organization) -> None:
    limit = plan_for(org)["dashboards"]
    if limit is None:
        return
    count = session.exec(select(func.count()).select_from(Dashboard).where(Dashboard.org_id == org.id)).one()
    if count >= limit:
        raise HTTPException(402, f"Dashboard limit reached for the {plan_for(org)['name']} plan ({limit}). Upgrade to continue.")
