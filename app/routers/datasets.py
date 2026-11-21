from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..engine import profiler
from ..models import Analysis, Dataset, Organization, User, utcnow
from ..plans import enforce_and_record
from ..security import current_org, current_user
from .analyses import _summary, ensure_dataset_owned, execute_analysis

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("", status_code=201)
async def upload_dataset(
    bg: BackgroundTasks,
    file: UploadFile = File(...),
    question: str | None = Form(default=None, max_length=500),
    user: User = Depends(current_user),
    org: Organization = Depends(current_org),
    session: Session = Depends(get_session),
):
    """Upload a CSV -> instant profiled dashboard. With a question and the AI engine on,
    also queue an AI analysis grounded in the dataset's profile + sample."""
    raw = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    try:
        columns, rows = profiler.parse_csv(raw)
        prof = profiler.profile(columns, rows)
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(422, f"Could not parse CSV: {exc}")

    enforce_and_record(session, org, "dataset")
    name = file.filename or "dataset.csv"
    ds = Dataset(org_id=org.id, name=name, rows=len(rows), columns=columns, profile=prof, sample=rows[:50])
    session.add(ds)
    session.flush()

    auto = Analysis(org_id=org.id, created_by=user.id, topic=f"Dataset: {name}", source="dataset",
                    dataset_id=ds.id, engine="profiler", status="done",
                    result=profiler.build_report(name, columns, rows, prof), completed_at=utcnow())
    session.add(auto)

    ai_analysis = None
    if question:
        enforce_and_record(session, org, "analysis")
        ai_analysis = Analysis(org_id=org.id, created_by=user.id, topic=question.strip(), source="dataset",
                               dataset_id=ds.id, engine="ai" if settings.ai_enabled else "demo")
        session.add(ai_analysis)
    session.commit()
    session.refresh(ds)
    session.refresh(auto)
    if ai_analysis:
        session.refresh(ai_analysis)
        bg.add_task(execute_analysis, ai_analysis.id, False,
                    profiler.compact_context(name, columns, rows, prof))
    return {"dataset": {"id": ds.id, "name": ds.name, "rows": ds.rows, "columns": ds.columns},
            "analysis": _summary(auto), "ai_analysis": _summary(ai_analysis) if ai_analysis else None}


@router.get("")
def list_datasets(org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    rows = session.exec(select(Dataset).where(Dataset.org_id == org.id).order_by(Dataset.created_at.desc())).all()
    return [{"id": d.id, "name": d.name, "rows": d.rows, "columns": d.columns, "created_at": d.created_at} for d in rows]


@router.get("/{dataset_id}")
def get_dataset(dataset_id: int, org: Organization = Depends(current_org), session: Session = Depends(get_session)):
    d = ensure_dataset_owned(session, dataset_id, org.id)
    return {"id": d.id, "name": d.name, "rows": d.rows, "columns": d.columns, "profile": d.profile,
            "sample": d.sample, "created_at": d.created_at}
