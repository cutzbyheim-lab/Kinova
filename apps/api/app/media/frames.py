"""Contact sheets: frames sampled across every source, tiled and labelled, so Claude can SEE the footage.

Each tile is stamped `S<source> HH:MM:SS.mmm`. A 4×4 sheet of 300px tiles costs about 1,900 input
tokens, so a whole production's visuals cost a couple of cents.
"""

import tempfile
from math import ceil
from pathlib import Path

from app.media.ffmpeg import run

TILE = 300
COLS = ROWS = 4
MAX_TILES = 64
MIN_STEP_S = 2.0
FONT_CANDIDATES = [
    "/usr/share/fonts/kinova/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
]


def _font() -> str | None:
    return next((f for f in FONT_CANDIDATES if Path(f).is_file()), None)


def sample_step(durations: list[float]) -> float:
    return max(MIN_STEP_S, sum(durations) / MAX_TILES)


def contact_sheets(sources: list[tuple[Path, float]]) -> tuple[list[bytes], float]:
    """Returns JPEG sheets (in source order) and the sampling interval in seconds."""
    step = sample_step([d for _, d in sources])
    font = _font()
    sheets: list[bytes] = []
    with tempfile.TemporaryDirectory(prefix="kinova-sheets-") as tmp:
        for i, (path, duration) in enumerate(sources):
            n_frames = max(1, int(duration // step) + 1)
            n_sheets = ceil(n_frames / (COLS * ROWS))
            label = "drawtext=" + (f"fontfile={font}:" if font else "") + (
                f"text='S{i} %{{pts\\:hms}}':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=6"
            )
            vf = ",".join([
                # select (not fps): keeps each frame's own timestamp, so labels match the picture
                f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{step - 0.02:.3f})'",
                f"scale={TILE}:{TILE}:force_original_aspect_ratio=decrease",
                f"pad={TILE}:{TILE}:(ow-iw)/2:(oh-ih)/2:color=0x15110F",
                label,
                f"tile={COLS}x{ROWS}:padding=4:color=0x15110F",
            ])
            out = Path(tmp) / f"s{i}_%02d.jpg"
            run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-vf", vf, "-fps_mode", "passthrough", "-frames:v", str(n_sheets),
                 "-q:v", "6", str(out)], timeout=600)
            sheets += [p.read_bytes() for p in sorted(Path(tmp).glob(f"s{i}_*.jpg"))]
    return sheets, step
