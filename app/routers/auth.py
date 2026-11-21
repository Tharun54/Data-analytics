from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from ..db import get_session
from ..models import Organization, User
from ..plans import PLANS, plan_for, usage_this_month
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    company: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _token_response(user: User) -> dict:
    return {"access_token": create_token(user), "token_type": "bearer"}


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, session: Session = Depends(get_session)):
    email = body.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "An account with this email already exists")
    org = Organization(name=body.company)
    session.add(org)
    session.flush()
    user = User(email=email, name=body.name, password_hash=hash_password(body.password), org_id=org.id)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _token_response(user)


@router.post("/auth/login")
def login(body: LoginIn, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email.lower())).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return _token_response(user)


@router.get("/me")
def me(user: User = Depends(current_user), session: Session = Depends(get_session)):
    from ..config import settings
    org = session.get(Organization, user.org_id)
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role},
        "org": {"id": org.id, "name": org.name, "plan": org.plan},
        "plan": plan_for(org),
        "usage": {k: usage_this_month(session, org.id, k) for k in ("analysis", "dataset")},
        "engine": "ai" if settings.ai_enabled else "demo",
    }


@router.get("/plans")
def plans():
    return PLANS
