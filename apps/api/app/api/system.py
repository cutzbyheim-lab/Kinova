from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.projects import project_out
from app.api.serializers import job_out, output_out
from app.ai.llm import ClaudeLLM, NotConfigured, explain_error
from app.core.config import get_settings
from app.media import motion
from app.core.context import RequestContext, get_ctx
from app.core.db import get_db
from app.models import AIGeneration, Brand, GeneratedAsset, MediaAsset, Organization, ProductionJob, Project

router = APIRouter(tags=["system"])


@router.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    return {"ok": True}


def _worker_status() -> dict:
    try:
        from app.workers.celery_app import celery_app

        replies = celery_app.control.ping(timeout=0.8)
        return {"online": bool(replies), "count": len(replies)}
    except Exception as e:
        return {"online": False, "count": 0, "error": type(e).__name__}


@router.get("/api/system/status")
def system_status(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    s = get_settings()
    org = db.get(Organization, ctx.org_id)
    return {
        "mode": "local",
        "organization": {"id": str(ctx.org_id), "name": org.name if org else "", "plan": org.plan if org else "free"},
        "worker": _worker_status(),
        "integrations": {
            "claude": {
                "configured": s.anthropic_configured,
                "models": {"fast": s.model_fast, "smart": s.model_smart},
                "env": "ANTHROPIC_API_KEY",
            },
            "youtube": {"configured": s.youtube_configured, "region": s.youtube_region, "env": "YOUTUBE_API_KEY"},
            "pexels": {"configured": s.pexels_configured, "env": "PEXELS_API_KEY"},
            "motion": (lambda ok_why: {"configured": ok_why[0], "detail": ok_why[1], "env": "MOTION_ENABLED"})(motion.available()),
            "whisper": {"configured": s.whisper_enabled, "model": s.whisper_model, "env": "WHISPER_ENABLED"},
        },
        "limits": {
            "max_upload_mb": s.max_upload_mb,
            "max_video_seconds": s.max_video_seconds,
            "max_job_cost_usd": s.max_job_cost_usd,
        },
    }


@router.post("/api/system/check-claude")
def check_claude(ctx: RequestContext = Depends(get_ctx)):
    """Makes one tiny Haiku call (a fraction of a cent) to prove the key really works."""
    s = get_settings()
    try:
        llm = ClaudeLLM(budget_usd=0.01)
        reply = llm.complete("connection_test", "fast", "You are a connection test.", "Reply with exactly: OK", max_tokens=5)
    except NotConfigured:
        return {"ok": False, "error": "No key set. Add ANTHROPIC_API_KEY to the .env file and restart KINOVA."}
    except Exception as e:  # auth, billing, network…
        return {"ok": False, "error": explain_error(e)}
    return {"ok": True, "model": s.model_fast, "reply": reply.text.strip()[:20]}


@router.get("/api/overview")
def overview(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    org = ctx.org_id
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    count = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    stats = {
        "projects": count(select(func.count()).where(Project.org_id == org, Project.status == "active")),
        "uploads": count(select(func.count()).where(MediaAsset.org_id == org, MediaAsset.kind != "audio")),
        "music_tracks": count(select(func.count()).where(MediaAsset.org_id == org, MediaAsset.kind == "audio")),
        "clips_ready": count(select(func.count()).where(GeneratedAsset.org_id == org, GeneratedAsset.status == "ready")),
        "clips_approved": count(select(func.count()).where(GeneratedAsset.org_id == org, GeneratedAsset.approved.is_(True))),
        "jobs_running": count(select(func.count()).where(
            ProductionJob.org_id == org, ProductionJob.status.in_(["queued", "running"]))),
        "brands": count(select(func.count()).where(Brand.org_id == org)),
        "ai_spend_month_usd": float(db.scalar(select(func.coalesce(func.sum(AIGeneration.cost_usd), 0)).where(
            AIGeneration.org_id == org, AIGeneration.created_at >= month_start)) or 0),
        "footage_minutes": round(float(db.scalar(select(func.coalesce(func.sum(MediaAsset.duration_s), 0)).where(
            MediaAsset.org_id == org, MediaAsset.kind == "video")) or 0) / 60, 1),
    }
    active = db.scalar(
        select(ProductionJob).where(ProductionJob.org_id == org, ProductionJob.status.in_(["queued", "running"]))
        .order_by(ProductionJob.created_at.desc()).limit(1)
    )
    latest = db.scalar(select(ProductionJob).where(ProductionJob.org_id == org).order_by(ProductionJob.created_at.desc()).limit(1))
    return {
        "stats": stats,
        "active_job": job_out(active) if active else None,
        "latest_job": job_out(latest) if latest else None,
        "recent_jobs": [job_out(j) for j in db.scalars(
            select(ProductionJob).where(ProductionJob.org_id == org).order_by(ProductionJob.created_at.desc()).limit(6))],
        "recent_outputs": [output_out(o) for o in db.scalars(
            select(GeneratedAsset).where(GeneratedAsset.org_id == org, GeneratedAsset.status == "ready")
            .order_by(GeneratedAsset.created_at.desc()).limit(8))],
        "projects": [project_out(db, p) for p in db.scalars(
            select(Project).where(Project.org_id == org, Project.status == "active").order_by(Project.updated_at.desc()).limit(4))],
        "brand": (lambda b: {"id": str(b.id), "name": b.name, "voice": b.voice, "colors": b.colors} if b else None)(
            db.scalar(select(Brand).where(Brand.org_id == org).order_by(Brand.created_at.desc()).limit(1))),
    }
