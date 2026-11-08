"""A tiny synthesized SFX kit (no downloads, fully deterministic): whoosh and pop."""

from pathlib import Path

from app.core.config import get_settings
from app.media.ffmpeg import run

SOURCES = {
    # pink-noise swell, band-limited, fast attack + decay
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink:a=0.9:r=48000",
               "-af", "highpass=f=350,lowpass=f=5200,afade=t=in:d=0.32:curve=exp,afade=t=out:st=0.32:d=0.18,volume=1.6"],
    # pitch-drop pop with a quick decay
    "pop": ["-f", "lavfi", "-i", "aevalsrc='0.9*sin(2*PI*(170+520*exp(-t*28))*t)*exp(-t*16)':d=0.3:s=48000"],
}


def sfx_path(name: str) -> Path:
    d = Path(get_settings().storage_dir) / "sfx"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.wav"
    if not p.is_file():
        tmp = p.with_suffix(".tmp.wav")
        run(["ffmpeg", "-y", "-v", "error", *SOURCES[name], "-ac", "2", str(tmp)], timeout=60)
        tmp.replace(p)
    return p
