import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import IdMixin, OrgScopedMixin, TimestampMixin, utcnow

STAGES = ["ingest", "transcribe", "trends", "plan", "assets", "render", "qc", "copy", "deliver"]


class ProductionJob(IdMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "production_jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    # queued | running | succeeded | partial | failed
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    # what the user asked for: topic, goal, platform, variations
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    # per-stage outputs (keys of stored artifacts, summaries) — enables resumable, idempotent runs
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 5), default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobEvent(IdMixin, Base):
    """Workflow history: one row per stage transition, shown live in the Studio."""

    __tablename__ = "job_events"

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("production_jobs.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(30))
    # started | done | skipped | warning | failed
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class GeneratedAsset(IdMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "generated_assets"

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("production_jobs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    variation_key: Mapped[str] = mapped_column(String(40))
    style: Mapped[str] = mapped_column(String(60), default="")
    aspect: Mapped[str] = mapped_column(String(10), default="9:16")
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    hook: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    cta: Mapped[str] = mapped_column(Text, default="")
    edit_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    qc: Mapped[dict] = mapped_column(JSON, default=dict)
    # rendering | ready | failed
    status: Mapped[str] = mapped_column(String(20), default="rendering")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
