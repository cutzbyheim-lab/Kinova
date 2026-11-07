import uuid

from app.core.db import SessionLocal
from app.models import Organization, Project
from tests.conftest import make_project, upload


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_system_status_reports_missing_keys(client):
    s = client.get("/api/system/status").json()
    assert s["mode"] == "local"
    assert s["integrations"]["claude"]["configured"] is False
    assert s["integrations"]["youtube"]["configured"] is False


def test_brand_crud_and_validation(client):
    bad = client.post("/api/brands", json={"name": "X", "colors": ["orange"]})
    assert bad.status_code == 422
    r = client.post("/api/brands", json={"name": "CutsByH", "voice": "direct, warm", "colors": ["#ff6a2b"]})
    assert r.status_code == 201
    brand = r.json()
    assert brand["colors"] == ["#FF6A2B"]
    r = client.patch(f"/api/brands/{brand['id']}", json={"audience": "18-34 locals"})
    assert r.json()["audience"] == "18-34 locals"
    assert len(client.get("/api/brands").json()) == 1
    assert client.delete(f"/api/brands/{brand['id']}").status_code == 204


def test_project_crud(client):
    p = make_project(client)
    assert p["asset_count"] == 0
    r = client.patch(f"/api/projects/{p['id']}", json={"status": "archived"})
    assert r.json()["status"] == "archived"
    assert client.get("/api/projects").json() == []
    assert len(client.get("/api/projects?status=archived").json()) == 1


def test_upload_validation(client, tmp_path, sample_video):
    p = make_project(client)
    txt = tmp_path / "notes.txt"
    txt.write_text("hello")
    with open(txt, "rb") as f:
        r = client.post(f"/api/projects/{p['id']}/media", files={"file": ("notes.txt", f, "text/plain")})
    assert r.status_code == 415
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"not really a video" * 100)
    with open(fake, "rb") as f:
        r = client.post(f"/api/projects/{p['id']}/media", files={"file": ("fake.mp4", f, "video/mp4")})
    assert r.status_code == 422

    m = upload(client, p["id"], sample_video, "My Raw Take (1).mp4")
    assert m["kind"] == "video"
    assert m["filename"] == "My-Raw-Take-1.mp4"
    assert abs(m["duration_s"] - 30) < 0.5
    assert m["thumbnail_url"]
    assert client.get(m["thumbnail_url"]).status_code == 200


def test_signed_urls_reject_tampering(client, sample_video):
    p = make_project(client)
    m = upload(client, p["id"], sample_video)
    good = m["url"]
    assert client.get(good).status_code == 200
    tampered = good.replace("sig=", "sig=0")
    assert client.get(tampered).status_code == 403


def test_tenant_isolation(client):
    make_project(client)  # creates the local org
    with SessionLocal() as db:
        other = Organization(name="Someone else", slug=f"other-{uuid.uuid4().hex[:6]}")
        db.add(other)
        db.flush()
        foreign = Project(org_id=other.id, name="Not yours")
        db.add(foreign)
        db.commit()
        foreign_id = foreign.id
    assert client.get(f"/api/projects/{foreign_id}").status_code == 404
    assert all(p["id"] != str(foreign_id) for p in client.get("/api/projects").json())
    assert client.delete(f"/api/projects/{foreign_id}").status_code == 404
