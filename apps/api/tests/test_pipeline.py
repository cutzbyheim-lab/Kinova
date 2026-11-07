from tests.conftest import make_project, upload


def test_full_production_without_keys(client, sample_video):
    """No Claude/YouTube keys: the pipeline must still deliver, and say exactly what it skipped."""
    brand = client.post("/api/brands", json={"name": "Test Brand", "colors": ["#7C5CFF"]}).json()
    p = make_project(client, brand_id=brand["id"])
    m = upload(client, p["id"], sample_video)

    r = client.post(f"/api/projects/{p['id']}/jobs", json={"source_asset_id": m["id"], "goal": "get bookings"})
    assert r.status_code == 201, r.text
    job = client.get(f"/api/jobs/{r.json()['id']}").json()

    assert job["status"] == "succeeded", job
    assert job["planner"] == "heuristic"
    assert job["cost_usd"] == 0
    by_stage = {e["stage"]: e for e in job["events"] if e["status"] in ("done", "skipped")}
    assert by_stage["transcribe"]["status"] == "skipped"
    assert by_stage["trends"]["status"] == "skipped"
    assert "YouTube is not connected" in by_stage["trends"]["message"]
    assert "not AI" in by_stage["plan"]["message"]
    assert by_stage["copy"]["status"] == "skipped"

    outs = job["outputs"]
    assert len(outs) == 3
    for o in outs:
        assert o["status"] == "ready"
        assert (o["width"], o["height"]) == (1080, 1920)
        assert o["qc"]["passed"] is True
        assert client.get(o["url"]).status_code == 200
        assert client.get(o["download_url"]).headers["content-disposition"].startswith("attachment")

    lib = client.get("/api/outputs").json()
    assert len(lib) == 3
    r = client.patch(f"/api/outputs/{outs[0]['id']}", json={"approved": True, "caption": "Edited"})
    assert r.json()["approved"] is True

    ov = client.get("/api/overview").json()
    assert ov["stats"]["clips_ready"] == 3
    assert ov["stats"]["clips_approved"] == 1


def test_job_rejects_foreign_asset(client, sample_video):
    p1 = make_project(client)
    p2 = make_project(client, name="Other")
    m = upload(client, p1["id"], sample_video)
    r = client.post(f"/api/projects/{p2['id']}/jobs", json={"source_asset_id": m["id"]})
    assert r.status_code == 400


def test_rerun_creates_new_job(client, sample_video):
    p = make_project(client)
    m = upload(client, p["id"], sample_video)
    first = client.post(f"/api/projects/{p['id']}/jobs", json={"source_asset_id": m["id"], "variations": 1}).json()
    second = client.post(f"/api/jobs/{first['id']}/rerun").json()
    assert second["id"] != first["id"]
    assert second["status"] == "succeeded"
    assert len(client.get(f"/api/jobs?project_id={p['id']}").json()) == 2


def test_multi_clip_production_with_music(client, sample_video, tmp_path):
    import subprocess

    track = tmp_path / "chill-beat.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=520:duration=8",
                    "-c:a", "libmp3lame", str(track)], check=True)
    with open(track, "rb") as f:
        r = client.post("/api/music", files={"file": ("chill-beat.mp3", f, "audio/mpeg")}, data={"mood": "chill"})
    assert r.status_code == 201, r.text
    music = r.json()
    assert music["meta"] == {"title": "chill beat", "mood": "chill"}
    assert [m["id"] for m in client.get("/api/music").json()] == [music["id"]]

    p = make_project(client)
    a = upload(client, p["id"], sample_video, "take-1.mp4")
    b = upload(client, p["id"], sample_video, "take-2.mp4")
    assert all(m["kind"] != "audio" for m in client.get("/api/media").json())

    r = client.post(f"/api/projects/{p['id']}/jobs", json={
        "source_asset_ids": [a["id"], b["id"]], "music": "auto", "broll": True, "variations": 2})
    assert r.status_code == 201, r.text
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "succeeded", job
    assert len(job["sources_media"]) == 2
    assert "2 clips" in next(e["message"] for e in job["events"] if e["stage"] == "ingest" and e["status"] == "done")
    # story uses both sources
    story = next(o for o in job["outputs"] if o["variation_key"] == "story")
    assert {c["source"] for c in story["edit_plan"]["clips"]} == {0, 1}
    assert story["edit_plan"]["music_title"] == "chill beat"
    # B-roll requested but Pexels not connected → honest warning, no fake footage
    assert any("Pexels is not connected" in w for w in job["warnings"])
    assert all(o["edit_plan"]["credits"] == [] for o in job["outputs"])


def test_job_rejects_audio_as_footage(client, sample_video, tmp_path):
    import subprocess

    track = tmp_path / "t.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=duration=3", str(track)], check=True)
    with open(track, "rb") as f:
        music = client.post("/api/music", files={"file": ("t.mp3", f, "audio/mpeg")}).json()
    p = make_project(client)
    v = upload(client, p["id"], sample_video)
    r = client.post(f"/api/projects/{p['id']}/jobs", json={"source_asset_ids": [v["id"], music["id"]]})
    assert r.status_code == 400
    r = client.post(f"/api/projects/{p['id']}/jobs", json={"source_asset_ids": [v["id"]], "music": v["id"]})
    assert r.status_code == 400
