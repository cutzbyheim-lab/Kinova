"""Deterministic FFmpeg renderer: executes one validated Variation into a vertical MP4."""

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
    out = out_dir / f"{variation.key}.mp4"
    total = variation.duration

    with tempfile.TemporaryDirectory(prefix="kinova-render-") as tmp:
        tmp_dir = Path(tmp)
        cues = chunk_words(words_for_cut(transcript, variation)) if with_subtitles else []
        hook = variation.hook_text if with_subtitles else ""
        ass_used = bool(cues or hook)
        if ass_used:
            (tmp_dir / "subs.ass").write_text(build_ass(cues, hook, variation.subtitle_position, accent, total), encoding="utf-8")

        parts: list[str] = []
        labels_v: list[str] = []
        labels_a: list[str] = []
        frame = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30,format=yuv420p"
        )
        for i, c in enumerate(variation.clips):
            parts.append(f"[0:v]trim=start={c.start}:end={c.end},setpts=PTS-STARTPTS,{frame}[v{i}]")
            labels_v.append(f"[v{i}]")
            if src_probe.has_audio:
                parts.append(f"[0:a]atrim=start={c.start}:end={c.end},asetpts=PTS-STARTPTS,aresample=48000[a{i}]")
                labels_a.append(f"[a{i}]")
        n = len(variation.clips)
        if src_probe.has_audio:
            interleaved = "".join(v + a for v, a in zip(labels_v, labels_a, strict=True))
            parts.append(f"{interleaved}concat=n={n}:v=1:a=1[vc][ac]")
            parts.append("[ac]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
        else:
            parts.append(f"{''.join(labels_v)}concat=n={n}:v=1:a=0[vc]")
        fonts_dir = next((d for d in FONTS_DIRS if Path(d).is_dir()), None)
        if ass_used:
            fd = f":fontsdir={fonts_dir}" if fonts_dir else ""
            parts.append(f"[vc]ass=subs.ass{fd}[vout]")
        else:
            parts.append("[vc]null[vout]")

        args = ["ffmpeg", "-y", "-v", "error", "-i", str(src.resolve())]
        if not src_probe.has_audio:
            args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        args += ["-filter_complex", ";".join(parts), "-map", "[vout]"]
        args += ["-map", "[aout]"] if src_probe.has_audio else ["-map", "1:a", "-shortest"]
        args += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out.resolve()),
        ]
        run(args, cwd=tmp_dir, timeout=1800)

    thumb = thumbnail(out, out_dir / f"{variation.key}.jpg", at=min(1.0, total / 3), width=540)
    return RenderOutput(video=out, thumb=thumb, duration=total, cue_count=len(cues))
