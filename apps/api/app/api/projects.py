import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import RequestContext, get_ctx, get_owned
from app.core.db import get_db
from app.core.signing import signed_url
from app.models import Brand, GeneratedAsset, MediaAsset, ProductionJob, Project
from app.schemas.api import ProjectIn, ProjectOut, ProjectPatch
from app.services.audit import audit
from app.services.storage import get_storage

router = APIRouter(prefix="/api/projects", tags=["projects"])


def project_out(db: Session, p: Project) -> ProjectOut:
    out = ProjectOut.model_validate(p)
    out.asset_count = db.scalar(select(func.count()).where(MediaAsset.project_id == p.id)) or 0
    out.output_count = db.scalar(
        select(func.count()).where(GeneratedAsset.project_id == p.id, GeneratedAsset.status == "ready")
    ) or 0
    cover = db.scalar(
        select(GeneratedAsset.thumbnail_key).where(GeneratedAsset.project_id == p.id, GeneratedAsset.status == "ready")
        .order_by(GeneratedAsset.created_at.desc()).limit(1)
    ) or db.scalar(
        select(MediaAsset.thumbnail_key).where(MediaAsset.project_id == p.id).order_by(MediaAsset.created_at.desc()).limit(1)
    )
    out.cover_url = signed_url(cover)
    out.latest_job_status = db.scalar(
        select(ProductionJob.status).where(ProductionJob.project_id == p.id)
        .order_by(ProductionJob.created_at.desc()).limit(1)
    )
    return out


@router.get("", response_model=list[ProjectOut])
def list_projects(status: str = "active", db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    rows = db.scalars(
        select(Project).where(Project.org_id == ctx.org_id, Project.status == status).order_by(Project.updated_at.desc())
    ).all()
    return [project_out(db, p) for p in rows]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    if body.brand_id:
        get_owned(db, Brand, body.brand_id, ctx)
    p = Project(org_id=ctx.org_id, **body.model_dump())
    db.add(p)
    db.flush()
    audit(db, ctx, "project.create", "project", p.id, name=p.name)
    db.commit()
    return project_out(db, p)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    return project_out(db, get_owned(db, Project, project_id, ctx))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: uuid.UUID, body: ProjectPatch, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    p = get_owned(db, Project, project_id, ctx)
    data = body.model_dump(exclude_unset=True)
    if data.get("brand_id"):
        get_owned(db, Brand, data["brand_id"], ctx)
    for k, v in data.items():
        setattr(p, k, v)
    audit(db, ctx, "project.update", "project", p.id, fields=list(data))
    db.commit()
    return project_out(db, p)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    p = get_owned(db, Project, project_id, ctx)
    storage = get_storage()
    for key in db.scalars(select(MediaAsset.storage_key).where(MediaAsset.project_id == p.id)):
        storage.delete_prefix(key.rsplit("/", 1)[0])
    for job_id in db.scalars(select(ProductionJob.id).where(ProductionJob.project_id == p.id)):
        storage.delete_prefix(f"orgs/{ctx.org_id}/generated/{job_id}")
    db.delete(p)
    audit(db, ctx, "project.delete", "project", project_id)
    db.commit()
