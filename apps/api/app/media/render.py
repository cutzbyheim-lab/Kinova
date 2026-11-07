"""Deterministic FFmpeg renderer: executes one validated Variation into a vertical MP4.

Memory-safe three-step render (works on an 8 GB laptop with long 4K footage):
  1. each clip is cut with input seeking and normalised (size, fps, audio) into its own segment
     — clips can come from different source videos,
  2. segments are joined losslessly with the concat demuxer,
  3. one final pass overlays stock B-roll, burns in captions, mixes music under the voice
     (sidechain ducking) and normalises loudness.
A single filtergraph with many trims of the same input buffers raw frames and can exhaust RAM.
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.media.ffmpeg import ProbeResult, run, thumbnail
from app.media.plan import BRoll, Variation
from app.media.subtitles import build_ass, chunk_words, words_for_cut

ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
FONTS_DIRS = ["/usr/share/fonts/kinova", "/usr/share/fonts"]


@dataclass
class RenderOutput:
    video: Path
    thumb: Path
    duration: float
    cue_count: int
    broll_used: int = 0
    music_used: bool = False


@dataclass
class Source:
    path: Path
    probe: ProbeResult


@dataclass
class Extras:
    broll: list[tuple[BRoll, Path]] = field(default_factory=list)
    music: Path | None = None
    music_volume: float = 0.15


def _frame(w: int, h: int) -> str:
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30,format=yuv420p"


def _cut_segment(src: Source, start: float, dur: float, w: int, h: int, out: Path) -> None:
    args = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src.path.resolve())]
    if src.probe.has_audio:
        args += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                 "-map", "0:v:0", "-map", "1:a:0"]
    args += [
        "-vf", _frame(w, h), "-af", "aresample=48000,aformat=channel_layouts=stereo",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", "60",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", f"{dur:.3f}", str(out),
    ]
    run(args, timeout=1800)


def render_variation(
    sources: list[Source],
    variation: Variation,
    transcripts: list | dict | None,
    out_dir: Path,
    accent: str = "#FF6A2B",
    aspect: str = "9:16",
    with_subtitles: bool = True,
    extras: Extras | None = None,
) -> RenderOutput:
    w, h = ASPECTS.get(aspect, ASPECTS["9:16"])
    extras = extras or Extras()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = (out_dir / f"{variation.key}.mp4").resolve()
    total = variation.duration

    with tempfile.TemporaryDirectory(prefix="kinova-render-") as tmp:
        tmp_dir = Path(tmp)
        # 1. segments (any source)
        seg_paths = []
        for i, c in enumerate(variation.clips):
            seg = tmp_dir / f"seg{i:02d}.mp4"
            _cut_segment(sources[c.source], c.start, c.end - c.start, w, h, seg)
            seg_paths.append(seg)
        # 2. join
        (tmp_dir / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in seg_paths))
        joined = tmp_dir / "joined.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", str(joined)],
            cwd=tmp_dir, timeout=600)

        # 3. B-roll + captions + music + loudness
        cues = chunk_words(words_for_cut(transcripts, variation)) if with_subtitles else []
        hook = variation.hook_text if with_subtitles else ""
        args = ["ffmpeg", "-y", "-v", "error", "-i", str(joined)]
        parts: list[str] = []
        cur = "[0:v]"
        idx = 1
        for j, (b, path) in enumerate(extras.broll):
            args += ["-i", str(path.resolve())]
            end = b.at + b.duration
            parts.append(f"[{idx}:v]trim=duration={b.duration:.2f},setpts=PTS-STARTPTS+{b.at:.2f}/TB,{_frame(w, h)}[b{j}]")
            parts.append(f"{cur}[b{j}]overlay=enable='between(t,{b.at:.2f},{end:.2f})':eof_action=pass[o{j}]")
            cur = f"[o{j}]"
            idx += 1
        if cues or hook:
            (tmp_dir / "subs.ass").write_text(
                build_ass(cues, hook, variation.subtitle_position, accent, total), encoding="utf-8")
            fonts_dir = next((d for d in FONTS_DIRS if Path(d).is_dir()), None)
            parts.append(f"{cur}ass=subs.ass" + (f":fontsdir={fonts_dir}" if fonts_dir else "") + "[vout]")
            cur = "[vout]"
        video_filtered = cur != "[0:v]"

        loud = "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"
        if extras.music:
            args += ["-stream_loop", "-1", "-i", str(extras.music.resolve())]
            parts.append("[0:a]asplit=2[voice][sc]")
            parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={extras.music_volume:.3f}[mus]")
            parts.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350[duck]")
            parts.append(f"[voice][duck]amix=inputs=2:duration=first:normalize=0,{loud}[aout]")
        else:
            parts.append(f"[0:a]{loud}[aout]")

        args += ["-filter_complex", ";".join(parts)]
        if video_filtered:
            args += ["-map", cur, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"]
        else:
            args += ["-map", "0:v", "-c:v", "copy"]
        args += ["-map", "[aout]", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}",
                 "-movflags", "+faststart", str(out)]
        run(args, cwd=tmp_dir, timeout=1800)

    thumb = thumbnail(out, out_dir / f"{variation.key}.jpg", at=min(1.0, total / 3), width=540)
    return RenderOutput(video=out, thumb=thumb, duration=total, cue_count=len(cues),
                        broll_used=len(extras.broll), music_used=extras.music is not None)
