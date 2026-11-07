import uuid
from datetime import date

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, BigInteger, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import IdMixin, OrgScopedMixin, TimestampMixin


class Brand(IdMixin, TimestampMixin, OrgScopedMixin, Base):
    """Brand Brain profile. The AI reads this on every generation."""

    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(200), default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    voice: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    products: Mapped[str] = mapped_column(Text, default="")
    goals: Mapped[str] = mapped_column(Text, default="")
    editing_style: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    colors: Mapped[list] = mapped_column(JSON, default=list)  # ["#FF6A2B", ...]
    fonts: Mapped[list] = mapped_column(JSON, default=list)
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class Project(IdMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(String(300), default="")
    # active | archived
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True
    )


class MediaAsset(IdMixin, TimestampMixin, OrgScopedMixin, Base):
    """Original uploaded media. Never modified; generated media lives in GeneratedAsset."""

    __tablename__ = "media_assets"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # video | image
    kind: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(400))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    thumbnail_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class Campaign(IdMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "campaigns"

    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text, default="")
    # draft | active | completed
    status: Mapped[str] = mapped_column(String(30), default="draft")
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
