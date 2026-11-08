"""Motion-graphics layer: runs the Remotion project in `apps/api/motion` for one cut.

The worker assembles the cut with FFmpeg, then this renders animated captions, the hook title,
B-roll entrances and the CTA over it (video only). Any failure raises MediaError and the
renderer falls back to the FFmpeg-only path, so a production never fails because of it.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.media.ffmpeg import MediaError, run

MOTION_DIR = Path(__file__).resolve().parents[2] / "motion"


def motion_dir() -> Path:
    return Path(get_settings().motion_dir or MOTION_DIR)


def available() -> tuple[bool, str]:
    s = get_settings()
    if not s.motion_enabled:
        return False, "turned off (MOTION_ENABLED=false)"
    if not shutil.which("node"):
        return False, "Node.js is not installed in the worker"
    d = motion_dir()
    if not (d / "render.mjs").is_file() or not (d / "build" / "index.html").is_file():
        return False, "the motion project isn't built (run `npm run bundle` in apps/api/motion)"
    return True, "ready"


def render_motion(props: dict, assets: dict[str, Path], out: Path, timeout: int = 1800) -> None:
    ok, why = available()
    if not ok:
        raise MediaError(f"Motion layer unavailable: {why}")
    s = get_settings()
    d = motion_dir()
    with tempfile.TemporaryDirectory(prefix="kinova-motion-") as tmp:
        tmp_dir = Path(tmp)
        assets_dir = tmp_dir / "assets"
        assets_dir.mkdir()
        for name, src in assets.items():
            if "/" in name or "\\" in name or name.startswith("."):
                raise MediaError(f"Bad asset name {name!r}")
            os.symlink(src.resolve(), assets_dir / name)
        props_file = tmp_dir / "props.json"
        props_file.write_text(json.dumps(props))
        env = dict(os.environ)
        if s.chrome_executable:
            env["CHROME_EXECUTABLE"] = s.chrome_executable
        if s.motion_concurrency:
            env["MOTION_CONCURRENCY"] = str(s.motion_concurrency)
        run(["node", str(d / "render.mjs"), "--props", str(props_file), "--assets", str(assets_dir),
             "--out", str(out.resolve()), "--bundle", str(d / "build")], timeout=timeout, cwd=d, env=env)
    if not out.is_file() or out.stat().st_size < 10_000:
        raise MediaError("Motion render produced no video")
