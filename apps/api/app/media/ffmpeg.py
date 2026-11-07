"""Thin, safe wrappers around ffprobe / ffmpeg (argument lists only, never shell strings)."""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class MediaError(Exception):
    pass


@dataclass
class ProbeResult:
    duration: float
    width: int | None
    height: int | None
    has_video: bool
    has_audio: bool
    video_codec: str | None = None
    audio_codec: str | None = None
    fps: float | None = None
    raw: dict = field(default_factory=dict)


def run(args: list[str], timeout: int = 1800, cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        raise MediaError(f"{args[0]} timed out after {timeout}s") from e
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-6:]
        raise MediaError(f"{args[0]} failed: " + " | ".join(tail))
    return proc


def probe(path: Path) -> ProbeResult:
    proc = run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        timeout=60,
    )
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(data.get("format", {}).get("duration") or (v or {}).get("duration") or 0)
    fps = None
    if v and v.get("avg_frame_rate", "0/0") not in ("0/0", ""):
        n, d = v["avg_frame_rate"].split("/")
        fps = float(n) / float(d) if float(d) else None
    width, height = (v or {}).get("width"), (v or {}).get("height")
    # Phones record portrait as landscape + rotation metadata
    rotation = 0
    for sd in (v or {}).get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = abs(int(sd["rotation"]))
    if rotation in (90, 270) and width and height:
        width, height = height, width
    return ProbeResult(
        duration=duration,
        width=width,
        height=height,
        has_video=v is not None,
        has_audio=a is not None,
        video_codec=(v or {}).get("codec_name"),
        audio_codec=(a or {}).get("codec_name"),
        fps=fps,
        raw=data,
    )


def thumbnail(src: Path, dest: Path, at: float, width: int = 640) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{max(at, 0):.2f}", "-i", str(src),
        "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(dest),
    ], timeout=120)
    return dest


def extract_audio(src: Path, dest: Path) -> Path:
    """16 kHz mono WAV — what Whisper expects."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(dest)])
    return dest
