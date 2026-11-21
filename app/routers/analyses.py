import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import settings
from ..db import engine as db_engine
from ..db import get_session
from ..engine import ai, demo
from ..models import Analysis, Dashboard, Dataset, Organization, User, utcnow
from ..plans import enforce_and_record, enforce_dashboard_limit, plan_for
from ..security import current_org, current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyses", tags=["analyses"])


class AnalysisIn(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    context: str | None = Field(default=None, max_length=20000, description="Optional notes or data to ground the analysis")


def execute_analysis(analysis_id: int, web_research: bool, context: str | None = None) -> None:
    """Runs in a background task with its own DB session."""
    with Session(db_engine) as session:
        a = session.get(Analysis, analysis_id)
        a.status = "running"
        session.commit()
        try:
            if a.engine == "ai":
                result = ai.run_topic_analysis(a.topic, web_research=web_research, context=context)
            else:
                result = demo.run_demo_analysis(a.topic)
            a.result, a.status = result, "done"
        except Exception as exc:  # surface a safe message to the customer, full trace to logs
            log.exception("analysis %s failed", analysis_id)
            a.status, a.error = "failed", ai.friendly_error(exc)
        a.completed_at = utcnow()
        session.commit()


def _get_owned(session: Session, analysis_id: int, org_id: int) -> Analysis:
    a = session.get(Analysis, analysis_id)
    if not a or a.org_id != org_id:
        raise HTTPException(404, "Analysis not found")
    return a


def _summary(a: Analysis) -> dict:
    return {"id": a.id, "topic": a.topic, "source": a.source, "engine": a.engine, "status": a.status,
            "error": a.error, "created_at": a.created_at, "completed_at": a.completed_at,
            "title": (a.result or {}).get("title")}


@router.post("", status_code=202)
def create_analysis(body: AnalysisIn, bg: BackgroundTasks, user: User = Depends(current_user),
                    org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    enforce_and_record(session, org, "analysis")
    a = Analysis(org_id=org.id, created_by=user.id, topic=body.topic.strip(),
                 engine="ai" if settings.ai_enabled else "demo")
    session.add(a)
    session.commit()
    session.refresh(a)
    bg.add_task(execute_analysis, a.id, plan_for(org)["web_research"], body.context)
    return _summary(a)


@router.get("")
def list_analyses(org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    rows = session.exec(select(Analysis).where(Analysis.org_id == org.id).order_by(Analysis.created_at.desc())).all()
    return [_summary(a) for a in rows]


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    a = _get_owned(session, analysis_id, org.id)
    return {**_summary(a), "result": a.result}


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: int, org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    a = _get_owned(session, analysis_id, org.id)
    for d in session.exec(select(Dashboard).where(Dashboard.org_id == org.id)).all():
        kept = [w for w in d.widgets if w.get("analysis_id") != a.id]
        if kept != d.widgets:
            d.widgets = kept
            session.add(d)
    session.delete(a)
    session.commit()


@router.post("/{analysis_id}/dashboard", status_code=201)
def dashboard_from_analysis(analysis_id: int, org: Organization = Depends(current_org),
                            session: Session = Depends(get_session)):
    """One click: turn a finished analysis into a dedicated dashboard with every widget."""
    a = _get_owned(session, analysis_id, org.id)
    if a.status != "done":
        raise HTTPException(409, "Analysis is not finished yet")
    enforce_dashboard_limit(session, org)
    r = a.result
    widgets = [{"analysis_id": a.id, "kind": "summary", "index": None}]
    widgets += [{"analysis_id": a.id, "kind": "kpi", "index": i} for i in range(len(r["kpis"]))]
    widgets += [{"analysis_id": a.id, "kind": "chart", "index": i} for i in range(len(r["charts"]))]
    if r["insights"]:
        widgets.append({"analysis_id": a.id, "kind": "insights", "index": None})
    if any(r["swot"].values()):
        widgets.append({"analysis_id": a.id, "kind": "swot", "index": None})
    if r["recommendations"]:
        widgets.append({"analysis_id": a.id, "kind": "recommendations", "index": None})
    d = Dashboard(org_id=org.id, name=r["title"], description=a.topic, widgets=widgets)
    session.add(d)
    session.commit()
    session.refresh(d)
    return {"id": d.id, "name": d.name}


def ensure_dataset_owned(session: Session, dataset_id: int, org_id: int) -> Dataset:
    ds = session.get(Dataset, dataset_id)
    if not ds or ds.org_id != org_id:
        raise HTTPException(404, "Dataset not found")
    return ds
