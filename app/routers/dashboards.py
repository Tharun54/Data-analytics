import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..models import Analysis, Dashboard, Organization, utcnow
from ..plans import PLANS, enforce_dashboard_limit, plan_for
from ..models import User
from ..security import current_org, current_user

router = APIRouter(tags=["dashboards"])

WidgetKind = Literal["summary", "kpi", "chart", "insights", "swot", "recommendations"]


class Widget(BaseModel):
    analysis_id: int
    kind: WidgetKind
    index: int | None = None


class DashboardIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    widgets: list[Widget] = Field(default_factory=list, max_length=100)


class DashboardPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    widgets: list[Widget] | None = Field(default=None, max_length=100)


def _validate_widgets(session: Session, org_id: int, widgets: list[Widget]) -> list[dict]:
    for w in widgets:
        a = session.get(Analysis, w.analysis_id)
        if not a or a.org_id != org_id:
            raise HTTPException(422, f"Analysis {w.analysis_id} not found")
    return [w.model_dump() for w in widgets]


def _resolve(session: Session, d: Dashboard) -> dict:
    """Expand widget references into renderable content. Missing pieces are dropped, not errors."""
    cache: dict[int, Analysis | None] = {}
    out = []
    for w in d.widgets:
        aid = w["analysis_id"]
        if aid not in cache:
            a = session.get(Analysis, aid)
            cache[aid] = a if a and a.org_id == d.org_id and a.status == "done" else None
        a = cache[aid]
        if not a:
            continue
        r = a.result
        kind, idx = w["kind"], w.get("index")
        if kind in ("kpi", "chart"):
            items = r["kpis" if kind == "kpi" else "charts"]
            if idx is None or not 0 <= idx < len(items):
                continue
            data = items[idx]
        elif kind == "summary":
            data = {"title": r["title"], "summary": r["summary"], "confidence": r["confidence"], "sources": r["sources"]}
        else:
            data = r[kind]
        out.append({**w, "data": data})
    return {"id": d.id, "name": d.name, "description": d.description, "widgets": out,
            "shared": bool(d.share_token), "share_token": d.share_token,
            "created_at": d.created_at, "updated_at": d.updated_at}


def _owned(session: Session, dashboard_id: int, org_id: int) -> Dashboard:
    d = session.get(Dashboard, dashboard_id)
    if not d or d.org_id != org_id:
        raise HTTPException(404, "Dashboard not found")
    return d


@router.get("/api/dashboards")
def list_dashboards(org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    rows = session.exec(select(Dashboard).where(Dashboard.org_id == org.id).order_by(Dashboard.updated_at.desc())).all()
    return [{"id": d.id, "name": d.name, "description": d.description, "widgets": len(d.widgets),
             "shared": bool(d.share_token), "updated_at": d.updated_at} for d in rows]


@router.post("/api/dashboards", status_code=201)
def create_dashboard(body: DashboardIn, org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    enforce_dashboard_limit(session, org)
    d = Dashboard(org_id=org.id, name=body.name, description=body.description,
                  widgets=_validate_widgets(session, org.id, body.widgets))
    session.add(d)
    session.commit()
    session.refresh(d)
    return _resolve(session, d)


@router.get("/api/dashboards/{dashboard_id}")
def get_dashboard(dashboard_id: int, org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    return _resolve(session, _owned(session, dashboard_id, org.id))


@router.patch("/api/dashboards/{dashboard_id}")
def update_dashboard(dashboard_id: int, body: DashboardPatch, org: Organization = Depends(current_org),
                     session: Session = Depends(get_session)):
    d = _owned(session, dashboard_id, org.id)
    if body.name is not None:
        d.name = body.name
    if body.description is not None:
        d.description = body.description
    if body.widgets is not None:
        d.widgets = _validate_widgets(session, org.id, body.widgets)
    d.updated_at = utcnow()
    session.add(d)
    session.commit()
    session.refresh(d)
    return _resolve(session, d)


@router.delete("/api/dashboards/{dashboard_id}", status_code=204)
def delete_dashboard(dashboard_id: int, org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    session.delete(_owned(session, dashboard_id, org.id))
    session.commit()


@router.post("/api/dashboards/{dashboard_id}/share")
def share_dashboard(dashboard_id: int, org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    if not plan_for(org)["sharing"]:
        raise HTTPException(402, "Public sharing is available on Pro and Business plans")
    d = _owned(session, dashboard_id, org.id)
    d.share_token = d.share_token or secrets.token_urlsafe(24)
    session.add(d)
    session.commit()
    return {"share_token": d.share_token, "url": f"/share/{d.share_token}"}


@router.delete("/api/dashboards/{dashboard_id}/share", status_code=204)
def unshare_dashboard(dashboard_id: int, org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    d = _owned(session, dashboard_id, org.id)
    d.share_token = None
    session.add(d)
    session.commit()


@router.get("/api/public/dashboards/{token}")
def public_dashboard(token: str, session: Session = Depends(get_session)):
    d = session.exec(select(Dashboard).where(Dashboard.share_token == token)).first()
    if not d:
        raise HTTPException(404, "Dashboard not found")
    data = _resolve(session, d)
    data.pop("share_token")
    return data


class PlanIn(BaseModel):
    plan: Literal["free", "pro", "business"]


@router.post("/api/billing/plan")
def change_plan(body: PlanIn, user: User = Depends(current_user), org: Organization = Depends(current_org),
                session: Session = Depends(get_session)):
    """Billing stub. In production this is called by the Stripe webhook after checkout succeeds,
    not directly by the browser — see docs/ROADMAP.md."""
    if user.role != "owner":
        raise HTTPException(403, "Only the workspace owner can change the plan")
    org.plan = body.plan
    session.add(org)
    session.commit()
    return {"plan": org.plan, "details": PLANS[org.plan]}
