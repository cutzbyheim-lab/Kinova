import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import job_out, media_out, output_out
from app.core.context import RequestContext, get_ctx, get_owned
from app.core.db import get_db
from app.models import Brand, GeneratedAsset, JobEvent, MediaAsset, ProductionJob, Project
from app.schemas.api import JobDetail, JobIn, JobOut, OutputOut, OutputPatch
from app.services.audit import audit

router = APIRouter(tags=["production"])


def _enqueue(db: Session, job: ProductionJob) -> None:
    from app.workers.tasks import run_production

    try:
        run_production.delay(str(job.id))
    except Exception as e:  # broker down
        job.status = "failed"
        job.error = "The production worker queue is unavailable. Is Redis/worker running?"
        db.commit()
        raise HTTPException(503, job.error) from e


def job_detail(db: Session, job: ProductionJob) -> JobDetail:
    base = job_out(job)
    detail = JobDetail(**base.model_dump())
    detail.events = db.scalars(select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.created_at)).all()  # type: ignore[assignment]
    detail.outputs = [output_out(o) for o in db.scalars(
        select(GeneratedAsset).where(GeneratedAsset.job_id == job.id).order_by(GeneratedAsset.created_at)
    )]
    src = db.get(MediaAsset, job.source_asset_id)
    detail.source_media = media_out(src) if src else None
    ids = job.settings.get("source_asset_ids") or [str(job.source_asset_id)]
    detail.sources_media = [media_out(m) for m in (db.get(MediaAsset, uuid.UUID(i)) for i in ids) if m]
    proj = db.get(Project, job.project_id)
    detail.project_name = proj.name if proj else ""
    return detail


@router.post("/api/projects/{project_id}/jobs", response_model=JobDetail, status_code=201)
def create_job(project_id: uuid.UUID, body: JobIn, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    project = get_owned(db, Project, project_id, ctx)
    ids = list(dict.fromkeys(body.source_asset_ids or ([body.source_asset_id] if body.source_asset_id else [])))
    if not ids:
        raise HTTPException(400, "Choose at least one video.")
    assets = []
    for aid in ids:
        asset = get_owned(db, MediaAsset, aid, ctx)
        if asset.project_id != project.id:
            raise HTTPException(400, f"“{asset.filename}” belongs to a different project.")
        if asset.kind != "video":
            raise HTTPException(400, f"“{asset.filename}” isn't a video.")
        assets.append(asset)
    if body.music not in ("auto", "none"):
        try:
            track = get_owned(db, MediaAsset, uuid.UUID(body.music), ctx)
        except ValueError:
            raise HTTPException(400, "Unknown music choice.") from None
        if track.kind != "audio":
            raise HTTPException(400, "That music choice isn't an audio track.")
    brand_id = body.brand_id or project.brand_id
    if brand_id:
        get_owned(db, Brand, brand_id, ctx)
    job = ProductionJob(
        org_id=ctx.org_id, project_id=project.id, source_asset_id=assets[0].id, brand_id=brand_id,
        settings={"topic": body.topic or project.topic, "goal": body.goal,
                  "platform": body.platform, "variations": body.variations,
                  "source_asset_ids": [str(a.id) for a in assets], "music": body.music, "broll": body.broll},
        result={},
    )
    db.add(job)
    db.flush()
    audit(db, ctx, "job.create", "job", job.id, project=str(project.id))
    db.commit()
    _enqueue(db, job)
    db.refresh(job)
    return job_detail(db, job)


@router.get("/api/jobs", response_model=list[JobOut])
def list_jobs(project_id: uuid.UUID | None = None, limit: int = 50, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    stmt = select(ProductionJob).where(ProductionJob.org_id == ctx.org_id)
    if project_id:
        stmt = stmt.where(ProductionJob.project_id == project_id)
    return [job_out(j) for j in db.scalars(stmt.order_by(ProductionJob.created_at.desc()).limit(min(limit, 200)))]


@router.get("/api/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    return job_detail(db, get_owned(db, ProductionJob, job_id, ctx))


@router.post("/api/jobs/{job_id}/retry", response_model=JobDetail)
def retry_job(job_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    """Resume a failed job; finished stages are not repeated (and not re-billed)."""
    job = get_owned(db, ProductionJob, job_id, ctx)
    if job.status not in ("failed", "partial"):
        raise HTTPException(409, f"Only failed or partial jobs can be retried (this one is {job.status}).")
    if job.status == "partial":
        # re-run render onwards so failed variations get another chance
        job.result = {k: v for k, v in job.result.items() if k not in ("render_done", "qc_done", "copy_done", "deliver_done")}
    job.status = "queued"
    job.error = None
    job.finished_at = None
    audit(db, ctx, "job.retry", "job", job.id)
    db.commit()
    _enqueue(db, job)
    db.refresh(job)
    return job_detail(db, job)


@router.post("/api/jobs/{job_id}/rerun", response_model=JobDetail, status_code=201)
def rerun_job(job_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    """Regenerate: a fresh job with the same footage and settings."""
    old = get_owned(db, ProductionJob, job_id, ctx)
    job = ProductionJob(
        org_id=ctx.org_id, project_id=old.project_id, source_asset_id=old.source_asset_id,
        brand_id=old.brand_id, settings=dict(old.settings), result={},
    )
    db.add(job)
    db.flush()
    audit(db, ctx, "job.rerun", "job", job.id, from_job=str(old.id))
    db.commit()
    _enqueue(db, job)
    db.refresh(job)
    return job_detail(db, job)


@router.get("/api/outputs", response_model=list[OutputOut])
def list_outputs(project_id: uuid.UUID | None = None, status: str | None = "ready", limit: int = 100,
                 db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    stmt = select(GeneratedAsset).where(GeneratedAsset.org_id == ctx.org_id)
    if project_id:
        stmt = stmt.where(GeneratedAsset.project_id == project_id)
    if status:
        stmt = stmt.where(GeneratedAsset.status == status)
    return [output_out(o) for o in db.scalars(stmt.order_by(GeneratedAsset.created_at.desc()).limit(min(limit, 500)))]


@router.patch("/api/outputs/{output_id}", response_model=OutputOut)
def update_output(output_id: uuid.UUID, body: OutputPatch, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    out = get_owned(db, GeneratedAsset, output_id, ctx)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(out, k, v)
    audit(db, ctx, "output.update", "output", out.id, fields=list(data))
    db.commit()
    return output_out(out)
