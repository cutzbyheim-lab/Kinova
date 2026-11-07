"""Automatic quality control for rendered outputs."""

from pathlib import Path

from app.media.ffmpeg import MediaError, probe

DURATION_TOLERANCE_S = 0.6
AV_SYNC_TOLERANCE_S = 0.25


def check_output(
    path: Path,
    expected_w: int,
    expected_h: int,
    expected_duration: float,
    expect_captions: bool,
    cue_count: int,
) -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    if not path.is_file() or path.stat().st_size < 10_000:
        add("file", False, "Output missing or empty")
        return {"passed": False, "checks": checks}
    add("file", True, f"{path.stat().st_size // 1024} KB")

    try:
        p = probe(path)
    except MediaError as e:
        add("readable", False, str(e))
        return {"passed": False, "checks": checks}
    add("readable", True)

    add("aspect", (p.width, p.height) == (expected_w, expected_h), f"{p.width}x{p.height}")
    add(
        "duration",
        abs(p.duration - expected_duration) <= DURATION_TOLERANCE_S,
        f"{p.duration:.2f}s vs planned {expected_duration:.2f}s",
    )
    add("audio_track", p.has_audio, "present" if p.has_audio else "missing")

    streams = p.raw.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    if v.get("duration") and a.get("duration"):
        drift = abs(float(v["duration"]) - float(a["duration"]))
        add("av_sync", drift <= AV_SYNC_TOLERANCE_S, f"stream drift {drift:.2f}s")

    if expect_captions:
        add("captions", cue_count > 0, f"{cue_count} caption cues")

    return {"passed": all(c["ok"] for c in checks), "checks": checks}
