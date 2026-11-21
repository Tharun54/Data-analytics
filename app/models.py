"""Database models. Multi-tenant: every business object belongs to an Organization."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    plan: str = Field(default="free")  # free | pro | business
    created_at: datetime = Field(default_factory=utcnow)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    password_hash: str
    role: str = Field(default="owner")  # owner | member
    org_id: int = Field(foreign_key="organization.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Analysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    created_by: int = Field(foreign_key="user.id")
    topic: str
    source: str = Field(default="topic")  # topic | dataset
    dataset_id: Optional[int] = Field(default=None, foreign_key="dataset.id")
    engine: str = Field(default="demo")  # ai | demo | profiler
    status: str = Field(default="pending")  # pending | running | done | failed
    error: Optional[str] = None
    result: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
    completed_at: Optional[datetime] = None


class Dataset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    name: str
    rows: int
    columns: list = Field(sa_column=Column(JSON))
    profile: dict = Field(sa_column=Column(JSON))
    sample: list = Field(sa_column=Column(JSON))  # first N rows for preview
    created_at: datetime = Field(default_factory=utcnow)


class Dashboard(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    name: str
    description: str = ""
    # [{"analysis_id": int, "kind": "kpi"|"chart"|"insights"|"swot"|"summary", "index": int|None}]
    widgets: list = Field(default_factory=list, sa_column=Column(JSON))
    share_token: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class UsageEvent(SQLModel, table=True):
    """Metering for plan limits and (later) usage-based billing."""
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    kind: str  # analysis | dataset
    created_at: datetime = Field(default_factory=utcnow, index=True)
