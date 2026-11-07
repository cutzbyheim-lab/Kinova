import hashlib
import re
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import media_out
from app.core.config import get_settings
from app.core.context import RequestContext, get_ctx, get_owned
from app.core.db import get_db
from app.core.signing import verify
from app.media.ffmpeg import MediaError, probe, thumbnail
from app.models import MediaAsset, Project
from app.schemas.api import MediaOut
from app.services.audit import audit
from app.services.storage import derived_key, get_storage, source_key

router = APIRouter(tags=["media"])

VIDEO_EXT = {".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska"}
IMAGE_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
CHUNK = 1024 * 1024


def _safe_name(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).stem).strip("-.")[:80] or "upload"
    return stem + Path(name).suffix.lower()


@router.post("/api/projects/{project_id}/media", response_model=MediaOut, status_code=201)
async def upload_media(
    project_id: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_ctx),
):
    settings = get_settings()
    project = get_owned(db, Project, project_id, ctx)
    name = _safe_name(file.filename or "upload")
    ext = Path(name).suffix
    if ext in VIDEO_EXT:
        kind, ctype = "video", VIDEO_EXT[ext]
    elif ext in IMAGE_EXT:
        kind, ctype = "image", IMAGE_EXT[ext]
    else:
        raise HTTPException(415, f"Unsupported file type '{ext or '?'}'. Use MP4, MOV, WEBM, MKV, JPG, PNG or WEBP.")

    limit = settings.max_upload_mb * CHUNK
    storage = get_storage()
    tmp_dir = storage.path("tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(dir=tmp_dir, suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > limit:
                tmp.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(413, f"File is larger than the {settings.max_upload_mb} MB limit.")
            sha.update(chunk)
            tmp.write(chunk)
    if size == 0:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, "The file is empty.")

    # Validate the *content*, not just the extension
    try:
        p = probe(tmp_path)
    except MediaError:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(422, "That file couldn't be read as media. It may be corrupt.") from None
    if kind == "video":
        if not p.has_video or p.duration <= 0:
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(422, "No playable video stream found in that file.")
        if p.duration > settings.max_video_seconds:
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(
                422, f"Video is {p.duration / 60:.1f} min; the limit is {settings.max_video_seconds // 60} min for now."
            )

    asset = MediaAsset(
        id=uuid.uuid4(), org_id=ctx.org_id, project_id=project.id, kind=kind, filename=name,
        content_type=ctype, size_bytes=size, sha256=sha.hexdigest(), storage_key="",
        duration_s=p.duration if kind == "video" else None, width=p.width, height=p.height,
        has_audio=p.has_audio, meta={"video_codec": p.video_codec, "audio_codec": p.audio_codec, "fps": p.fps},
    )
    asset.storage_key = storage.put_file(source_key(ctx.org_id, asset.id, name), tmp_path, move=True)
    try:
        thumb_key = derived_key(ctx.org_id, asset.id, "thumb.jpg")
        at = min(1.0, (p.duration or 0) / 4) if kind == "video" else 0
        thumbnail(storage.path(asset.storage_key), storage.path(thumb_key), at=at)
        asset.thumbnail_key = thumb_key
    except MediaError:
        asset.thumbnail_key = None
    db.add(asset)
    audit(db, ctx, "media.upload", "media", asset.id, filename=name, size=size)
    db.commit()
    return media_out(asset)


@router.get("/api/media", response_model=list[MediaOut])
def list_media(
    project_id: uuid.UUID | None = None,
    kind: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_ctx),
):
    stmt = select(MediaAsset).where(MediaAsset.org_id == ctx.org_id)
    if project_id:
        stmt = stmt.where(MediaAsset.project_id == project_id)
    if kind:
        stmt = stmt.where(MediaAsset.kind == kind)
    if q:
        stmt = stmt.where(MediaAsset.filename.ilike(f"%{q}%"))
    return [media_out(m) for m in db.scalars(stmt.order_by(MediaAsset.created_at.desc()).limit(500))]


@router.get("/api/media/{asset_id}", response_model=MediaOut)
def get_media(asset_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    return media_out(get_owned(db, MediaAsset, asset_id, ctx))


@router.delete("/api/media/{asset_id}", status_code=204)
def delete_media(asset_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    asset = get_owned(db, MediaAsset, asset_id, ctx)
    storage = get_storage()
    storage.delete_prefix(f"orgs/{ctx.org_id}/source/{asset.id}")
    storage.delete_prefix(f"orgs/{ctx.org_id}/derived/{asset.id}")
    db.delete(asset)
    audit(db, ctx, "media.delete", "media", asset_id)
    db.commit()


@router.get("/api/files/{key:path}", include_in_schema=False)
def serve_file(key: str, exp: int = Query(...), sig: str = Query(...), dl: int = 0):
    if not verify(key, exp, sig):
        raise HTTPException(403, "This link has expired or is invalid.")
    path = get_storage().path(key)
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=path.name if dl else None, headers={"Cache-Control": "private, max-age=3600"})
