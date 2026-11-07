import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX = r"^#[0-9A-Fa-f]{6}$"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Brands ---------------------------------------------------------------

class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry: str = Field(default="", max_length=200)
    audience: str = Field(default="", max_length=2000)
    voice: str = Field(default="", max_length=2000)
    personality: str = Field(default="", max_length=2000)
    products: str = Field(default="", max_length=4000)
    goals: str = Field(default="", max_length=2000)
    editing_style: str = Field(default="", max_length=2000)
    instructions: str = Field(default="", max_length=4000)
    colors: list[str] = Field(default_factory=list, max_length=8)
    fonts: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("colors")
    @classmethod
    def hex_colors(cls, v: list[str]) -> list[str]:
        import re

        bad = [c for c in v if not re.match(HEX, c)]
        if bad:
            raise ValueError(f"Colors must be #RRGGBB: {bad}")
        return [c.upper() for c in v]


class BrandPatch(BrandIn):
    name: str | None = Field(default=None, min_length=1, max_length=200)  # type: ignore[assignment]


class BrandOut(ORM, BrandIn):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- Projects -------------------------------------------------------------

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    topic: str = Field(default="", max_length=300)
    brand_id: uuid.UUID | None = None


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    topic: str | None = Field(default=None, max_length=300)
    brand_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class ProjectOut(ORM):
    id: uuid.UUID
    name: str
    description: str
    topic: str
    status: str
    brand_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    asset_count: int = 0
    output_count: int = 0
    cover_url: str | None = None
    latest_job_status: str | None = None


# --- Media ----------------------------------------------------------------

class MediaOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID | None
    kind: str
    filename: str
    content_type: str
    size_bytes: int
    duration_s: float | None
    width: int | None
    height: int | None
    has_audio: bool
    created_at: datetime
    url: str | None = None
    thumbnail_url: str | None = None


# --- Jobs -----------------------------------------------------------------

class JobIn(BaseModel):
    source_asset_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    topic: str = Field(default="", max_length=300)
    goal: str = Field(default="", max_length=1000)
    platform: str = Field(default="TikTok", pattern="^(TikTok|Instagram Reels|YouTube Shorts)$")
    variations: int = Field(default=3, ge=1, le=3)


class JobEventOut(ORM):
    stage: str
    status: str
    message: str
    created_at: datetime


class OutputOut(ORM):
    id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    variation_key: str
    style: str
    aspect: str
    status: str
    approved: bool
    duration_s: float | None
    width: int | None
    height: int | None
    title: str
    hook: str
    caption: str
    hashtags: list[str]
    cta: str
    edit_plan: dict
    qc: dict
    created_at: datetime
    url: str | None = None
    download_url: str | None = None
    thumbnail_url: str | None = None


class OutputPatch(BaseModel):
    approved: bool | None = None
    title: str | None = Field(default=None, max_length=300)
    hook: str | None = Field(default=None, max_length=1000)
    caption: str | None = Field(default=None, max_length=4000)
    hashtags: list[str] | None = Field(default=None, max_length=15)
    cta: str | None = Field(default=None, max_length=500)


class JobOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    source_asset_id: uuid.UUID
    brand_id: uuid.UUID | None
    status: str
    stage: str | None
    progress: int
    settings: dict
    error: str | None
    cost_usd: float
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    planner: str | None = None
    plan_summary: str | None = None
    trends: dict | None = None
    warnings: list[str] = []
    source: dict | None = None


class JobDetail(JobOut):
    events: list[JobEventOut] = []
    outputs: list[OutputOut] = []
    source_media: MediaOut | None = None
    project_name: str = ""


# --- Campaigns (foundation only in milestone 1) ---------------------------

class CampaignOut(ORM):
    id: uuid.UUID
    name: str
    goal: str
    status: str
    starts_on: date | None
    ends_on: date | None
