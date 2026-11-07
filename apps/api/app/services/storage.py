"""Private object storage.

Local-disk driver for milestone 1. Keys are namespaced so original uploads and
generated media never mix:
    orgs/<org>/source/<asset>/<file>
    orgs/<org>/derived/<asset>/...      (thumbnails, audio, transcripts)
    orgs/<org>/generated/<job>/<file>
An S3-compatible driver can implement the same four methods later.
"""

import shutil
import uuid
from pathlib import Path

from app.core.config import get_settings


class LocalStorage:
    def __init__(self, base: Path | None = None) -> None:
        self.base = Path(base or get_settings().storage_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        p = (self.base / key).resolve()
        if self.base not in p.parents and p != self.base:
            raise ValueError("Invalid storage key")
        return p

    def put_file(self, key: str, src: Path, move: bool = False) -> str:
        dest = self.path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        (shutil.move if move else shutil.copyfile)(str(src), str(dest))
        return key

    def put_bytes(self, key: str, data: bytes) -> str:
        dest = self.path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return key

    def exists(self, key: str | None) -> bool:
        return bool(key) and self.path(key).is_file()  # type: ignore[arg-type]

    def delete_prefix(self, prefix: str) -> None:
        p = self.path(prefix)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)


def source_key(org_id: uuid.UUID, asset_id: uuid.UUID, filename: str) -> str:
    return f"orgs/{org_id}/source/{asset_id}/{filename}"


def derived_key(org_id: uuid.UUID, asset_id: uuid.UUID, name: str) -> str:
    return f"orgs/{org_id}/derived/{asset_id}/{name}"


def generated_key(org_id: uuid.UUID, job_id: uuid.UUID, name: str) -> str:
    return f"orgs/{org_id}/generated/{job_id}/{name}"


_storage: LocalStorage | None = None


def get_storage() -> LocalStorage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage
