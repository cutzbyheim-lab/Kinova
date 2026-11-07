"""Deterministic FFmpeg renderer: executes one validated Variation into a vertical MP4.

Memory-safe three-step render (works on an 8 GB laptop with long 4K footage):
  1. each clip is cut with input seeking and normalised (size, fps, audio) into its own segment,
  2. segments are joined losslessly with the concat demuxer,
  3. one final pass burns in captions and normalises loudness.
A single filtergraph with many trims of the same input buffers raw frames and can exhaust RAM.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.media.ffmpeg import ProbeResult, run, thumbnail
from app.media.plan import Variation
from app.media.subtitles import build_ass, chunk_words, words_for_cut

ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
FONTS_DIRS = ["/usr/share/fonts/kinova", "/usr/share/fonts"]


@dataclass
class RenderOutput:
    video: Path
    thumb: Path
    duration: float
    cue_count: int


def _cut_segment(src: Path, has_audio: bool, start: float, dur: float, w: int, h: int, out: Path) -> None:
    frame = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30,format=yuv420p"
    args = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
    if has_audio:
        args += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                 "-map", "0:v:0", "-map", "1:a:0"]
    args += [
        "-vf", frame, "-af", "aresample=48000,aformat=channel_layouts=stereo",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", "60",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", f"{dur:.3f}", str(out),
    ]
    run(args, timeout=1800)


def render_variation(
    src: Path,
    src_probe: ProbeResult,
    variation: Variation,
    transcript: dict | None,
    out_dir: Path,
    accent: str = "#FF6A2B",
    aspect: str = "9:16",
    with_subtitles: bool = True,
) -> RenderOutput:
    w, h = ASPECTS.get(aspect, ASPECTS["9:16"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = (out_dir / f"{variation.key}.mp4").resolve()
    total = variation.duration
    src = src.resolve()

    with tempfile.TemporaryDirectory(prefix="kinova-render-") as tmp:
        tmp_dir = Path(tmp)
        # 1. segments
        seg_paths = []
        for i, c in enumerate(variation.clips):
            seg = tmp_dir / f"seg{i:02d}.mp4"
            _cut_segment(src, src_probe.has_audio, c.start, c.end - c.start, w, h, seg)
            seg_paths.append(seg)
        # 2. join
        (tmp_dir / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in seg_paths))
        joined = tmp_dir / "joined.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", str(joined)],
            cwd=tmp_dir, timeout=600)
        # 3. captions + loudness
        cues = chunk_words(words_for_cut(transcript, variation)) if with_subtitles else []
        hook = variation.hook_text if with_subtitles else ""
        args = ["ffmpeg", "-y", "-v", "error", "-i", str(joined)]
        if cues or hook:
            (tmp_dir / "subs.ass").write_text(
                build_ass(cues, hook, variation.subtitle_position, accent, total), encoding="utf-8")
            fonts_dir = next((d for d in FONTS_DIRS if Path(d).is_dir()), None)
            vf = "ass=subs.ass" + (f":fontsdir={fonts_dir}" if fonts_dir else "")
            args += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"]
        else:
            args += ["-c:v", "copy"]
        args += [
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
        ]
        run(args, cwd=tmp_dir, timeout=1800)

    thumb = thumbnail(out, out_dir / f"{variation.key}.jpg", at=min(1.0, total / 3), width=540)
    return RenderOutput(video=out, thumb=thumb, duration=total, cue_count=len(cues))
