import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# Configure BEFORE importing the app
_tmp = Path(tempfile.mkdtemp(prefix="kinova-test-"))
os.environ.update({
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://kinova:kinova@localhost:5432/kinova_test"),
    "STORAGE_DIR": str(_tmp / "storage"),
    "CELERY_EAGER": "true",
    "ANTHROPIC_API_KEY": "",
    "YOUTUBE_API_KEY": "",
    "WHISPER_ENABLED": "false",
    "MOTION_ENABLED": os.environ.get("TEST_MOTION", "false"),
    "SECRET_KEY": "test-secret",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.core.context import reset_ctx_cache  # noqa: E402
from app.core.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    reset_ctx_cache()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def sample_video() -> Path:
    """30s 1080p landscape test clip with a tone."""
    path = _tmp / "sample.mp4"
    if not path.exists():
        subprocess.run([
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=30",
            "-f", "lavfi", "-i", "sine=frequency=330:duration=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(path),
        ], check=True)
    return path


def make_project(client: TestClient, **kw) -> dict:
    r = client.post("/api/projects", json={"name": "Launch week", "topic": "barber fade tutorial", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def upload(client: TestClient, project_id: str, path: Path, name: str | None = None) -> dict:
    with open(path, "rb") as f:
        r = client.post(f"/api/projects/{project_id}/media", files={"file": (name or path.name, f, "video/mp4")})
    assert r.status_code == 201, r.text
    return r.json()
