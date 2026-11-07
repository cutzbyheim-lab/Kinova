"""Request context and tenant isolation.

Milestone 1 runs in *local single-user mode*: every request acts as one local user
inside one organization. The rest of the code only ever sees a `RequestContext`,
so swapping in real authentication later means replacing `get_ctx` — nothing else.
"""

import uuid
from dataclasses import dataclass
from typing import TypeVar

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Membership, Organization, User

LOCAL_EMAIL = "local@kinova.local"
LOCAL_ORG_SLUG = "local-studio"


@dataclass(frozen=True)
class RequestContext:
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str


def ensure_local_workspace(db: Session) -> RequestContext:
    org = db.scalar(select(Organization).where(Organization.slug == LOCAL_ORG_SLUG))
    if org is None:
        org = Organization(name="My Studio", slug=LOCAL_ORG_SLUG)
        db.add(org)
        db.flush()
    user = db.scalar(select(User).where(User.email == LOCAL_EMAIL))
    if user is None:
        user = User(email=LOCAL_EMAIL, name="Local user")
        db.add(user)
        db.flush()
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org.id, Membership.user_id == user.id)
    )
    if membership is None:
        membership = Membership(org_id=org.id, user_id=user.id, role="owner")
        db.add(membership)
    db.commit()
    return RequestContext(user_id=user.id, org_id=org.id, role=membership.role)


_cached: RequestContext | None = None


def get_ctx(db: Session = Depends(get_db)) -> RequestContext:
    global _cached
    if _cached is None:
        _cached = ensure_local_workspace(db)
    return _cached


def reset_ctx_cache() -> None:
    global _cached
    _cached = None


T = TypeVar("T")


def get_owned(db: Session, model: type[T], obj_id: uuid.UUID, ctx: RequestContext) -> T:
    """Fetch a tenant-owned row by id, enforcing organization ownership (404 otherwise)."""
    obj = db.scalar(select(model).where(model.id == obj_id, model.org_id == ctx.org_id))  # type: ignore[attr-defined]
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
