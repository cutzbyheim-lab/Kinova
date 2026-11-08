"""Deterministic renderer: executes one validated Variation into a vertical MP4.

Pipeline for one cut (memory-safe on an 8 GB laptop with long 4K footage):
  1. cut   — each clip is cut with input seeking, cropped on the subject (focus_x) with its
             punch-in zoom, normalised to 1080×1920 @30fps + stereo 48 kHz,
  2. join  — lossless concat of the segments,
  3. audio — voice + library music (sidechain-ducked under speech) + loudness normalisation,
  4. look  — the Remotion motion layer (animated captions, hook title, B-roll entrances, CTA);
             if it is unavailable or fails, an FFmpeg path (overlay B-roll + ASS captions) is used,
  5. finish — color grade, film grain, vignette over everything + SFX on the hits, muxed with audio.
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.media import motion
from app.media.ffmpeg import MediaError, ProbeResult, run, thumbnail
from app.media.plan import BRoll, Variation
from app.media.sfx import sfx_path
from app.media.subtitles import build_ass, chunk_words, words_for_cut

ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}
FONTS_DIRS = ["/usr/share/fonts/kinova", "/usr/share/fonts"]
FPS = 30
HOOK_MAX_S = 2.8
CTA_LEN_S = 2.4
MIN_CTA_CUT_S = 8.0
# Grade + grain + vignette, applied over everything (type included) like a film finish.
FINISH = "eq=contrast=1.05:saturation=1.08,vignette=angle=PI/5:mode=forward,noise=alls=5:allf=t+u,format=yuv420p"


@dataclass
class RenderOutput:
    video: Path
    thumb: Path
    duration: float
    cue_count: int
    broll_used: int = 0
    music_used: bool = False
    motion_used: bool = False
    motion_error: str | None = None


@dataclass
class Source:
    path: Path
    probe: ProbeResult


@dataclass
class Extras:
    broll: list[tuple[BRoll, Path]] = field(default_factory=list)
    music: Path | None = None
    music_volume: float = 0.15


def _crop_filter(w: int, h: int, focus_x: float, zoom: float) -> str:
    fy = 0.5 if zoom <= 1.0 else 0.42  # tighter shots keep a little more headroom
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"scale=trunc(iw*{zoom:.3f}/2)*2:trunc(ih*{zoom:.3f}/2)*2,"
        # center the window on the subject (focus_x = subject's horizontal position), clamped to the frame
        f"crop={w}:{h}:'max(0,min(iw-{w},iw*{focus_x:.3f}-{w}/2))':(ih-{h})*{fy},setsar=1,fps={FPS},format=yuv420p"
    )


def _cut_segment(src: Source, start: float, dur: float, w: int, h: int, out: Path,
                 focus_x: float = 0.5, zoom: float = 1.0) -> None:
    args = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src.path.resolve())]
    if src.probe.has_audio:
        args += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                 "-map", "0:v:0", "-map", "1:a:0"]
    args += [
        "-vf", _crop_filter(w, h, focus_x, zoom), "-af", "aresample=48000,aformat=channel_layouts=stereo",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-g", "60",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", f"{dur:.3f}", str(out),
    ]
    run(args, timeout=1800)


def _mix_audio(joined: Path, extras: Extras, out: Path, total: float, cwd: Path) -> None:
    """Video copied as-is; audio = voice (+ ducked music) → loudness-normalised."""
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(joined)]
    if extras.music:
        args += ["-stream_loop", "-1", "-i", str(extras.music.resolve()), "-filter_complex", ";".join([
            "[0:a]asplit=2[voice][sc]",
            f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={extras.music_volume:.3f}[mus]",
            "[mus][sc]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350[duck]",
            f"[voice][duck]amix=inputs=2:duration=first:normalize=0,{loud}[aout]",
        ])]
    else:
        args += ["-filter_complex", f"[0:a]{loud}[aout]"]
    args += ["-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-t", f"{total:.3f}", str(out)]
    run(args, cwd=cwd, timeout=1800)


def _ffmpeg_look(base: Path, variation: Variation, words: list, extras: Extras, accent: str,
                 total: float, w: int, h: int, out: Path, cwd: Path) -> int:
    """Fallback look without the motion layer: B-roll hard overlays + ASS captions. Returns caption cue count."""
    cues = chunk_words(words) if words else []
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(base)]
    parts: list[str] = []
    cur = "[0:v]"
    frame = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={FPS},format=yuv420p"
    for j, (b, path) in enumerate(extras.broll):
        args += ["-i", str(path.resolve())]
        parts.append(f"[{j + 1}:v]trim=duration={b.duration:.2f},setpts=PTS-STARTPTS+{b.at:.2f}/TB,{frame}[b{j}]")
        parts.append(f"{cur}[b{j}]overlay=enable='between(t,{b.at:.2f},{b.at + b.duration:.2f})':eof_action=pass[o{j}]")
        cur = f"[o{j}]"
    hook = variation.hook_text if words is not None else ""
    if cues or hook:
        (cwd / "subs.ass").write_text(build_ass(cues, hook, variation.subtitle_position, accent, total), encoding="utf-8")
        fonts_dir = next((d for d in FONTS_DIRS if Path(d).is_dir()), None)
        parts.append(f"{cur}ass=subs.ass" + (f":fontsdir={fonts_dir}" if fonts_dir else "") + "[vout]")
        cur = "[vout]"
    if cur == "[0:v]":
        parts.append("[0:v]null[vout]")
        cur = "[vout]"
    args += ["-filter_complex", ";".join(parts), "-map", cur, "-an",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-t", f"{total:.3f}", str(out)]
    run(args, cwd=cwd, timeout=1800)
    return len(cues)


def _finish(look: Path, audio_src: Path, sfx: list[tuple[str, float, float]], total: float, out: Path, cwd: Path) -> None:
    """Grade + grain + vignette over the finished picture, audio from the mix, SFX on the hits."""
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(look), "-i", str(audio_src)]
    parts = [f"[0:v]{FINISH}[vout]"]
    labels = ["[1:a]"]
    for k, (name, at, vol) in enumerate(sfx):
        args += ["-i", str(sfx_path(name))]
        delay = max(0, int(at * 1000))
        parts.append(f"[{k + 2}:a]adelay={delay}|{delay},volume={vol:.2f}[s{k}]")
        labels.append(f"[s{k}]")
    if len(labels) > 1:
        parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,alimiter=limit=0.95[aout]")
        amap = "[aout]"
    else:
        amap = "1:a"
    args += ["-filter_complex", ";".join(parts), "-map", "[vout]", "-map", amap,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
    run(args, cwd=cwd, timeout=1800)


def timings(variation: Variation, total: float, with_text: bool) -> tuple[float, float]:
    """(hook_end, cta_start) in seconds. hook_end 0 = no hook; cta_start >= total = no CTA."""
    hook_end = min(HOOK_MAX_S, total * 0.4) if with_text and variation.hook_text.strip() else 0.0
    cta_start = total
    if with_text and variation.cta_text.strip() and total >= MIN_CTA_CUT_S:
        cta_start = max(total - CTA_LEN_S, hook_end + 1.0)
    return hook_end, cta_start


def render_variation(
    sources: list[Source],
    variation: Variation,
    transcripts: list | dict | None,
    out_dir: Path,
    accent: str = "#FF6A2B",
    aspect: str = "9:16",
    with_subtitles: bool = True,
    extras: Extras | None = None,
    accent2: str = "#9A80FF",
    use_motion: bool = True,
) -> RenderOutput:
    w, h = ASPECTS.get(aspect, ASPECTS["9:16"])
    extras = extras or Extras()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = (out_dir / f"{variation.key}.mp4").resolve()
    total = variation.duration
    words = words_for_cut(transcripts, variation) if with_subtitles else []
    hook_end, cta_start = timings(variation, total, with_subtitles)

    with tempfile.TemporaryDirectory(prefix="kinova-render-") as tmp:
        tmp_dir = Path(tmp)
        # 1–2. cut + join
        seg_paths = []
        for i, c in enumerate(variation.clips):
            seg = tmp_dir / f"seg{i:02d}.mp4"
            _cut_segment(sources[c.source], c.start, c.end - c.start, w, h, seg, c.focus_x, c.zoom)
            seg_paths.append(seg)
        (tmp_dir / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in seg_paths))
        joined = tmp_dir / "joined.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", str(joined)],
            cwd=tmp_dir, timeout=600)
        # 3. audio mix
        base = tmp_dir / "base.mp4"
        _mix_audio(joined, extras, base, total, tmp_dir)

        # 4. look
        look = tmp_dir / "look.mp4"
        motion_used, motion_error, cue_count = False, None, 0
        if use_motion:
            segments, t = [], 0.0
            for c in variation.clips:
                segments.append(round(t, 3))
                t += c.end - c.start
            assets = {"base.mp4": base}
            shots = []
            for k, (b, p) in enumerate(extras.broll):
                name = f"broll-{k}{p.suffix.lower() or '.mp4'}"
                assets[name] = p
                shots.append({"src": name, "at": b.at, "duration": b.duration})
            props = {
                "video": "base.mp4", "width": w, "height": h, "fps": FPS,
                "durationInFrames": max(1, round(total * FPS)),
                "colors": {"hero": accent, "accent": accent2},
                "segments": segments,
                "hook": variation.hook_text if hook_end else "",
                "words": [{"start": round(x["start"], 3), "end": round(x["end"], 3), "text": x["word"]} for x in words],
                "captionPosition": variation.subtitle_position,
                "broll": shots,
                "cta": variation.cta_text if cta_start < total else "",
                "hookEnd": hook_end,
                "ctaStart": cta_start,
            }
            try:
                motion.render_motion(props, assets, look)
                motion_used = True
                cue_count = len(words)
            except MediaError as e:
                motion_error = str(e)
        if not motion_used:
            cue_count = _ffmpeg_look(base, variation, words if with_subtitles else None, extras, accent, total, w, h, look, tmp_dir)

        # 5. finish + SFX on the hits (2–3 frames before the visual lands)
        sfx: list[tuple[str, float, float]] = []
        if hook_end:
            sfx.append(("whoosh", 0.0, 0.32))
        for b, _ in extras.broll:
            sfx.append(("whoosh", max(0.0, b.at - 0.08), 0.28))
        if cta_start < total:
            sfx.append(("pop", cta_start + 0.05, 0.45))
        _finish(look, base, sfx, total, out, tmp_dir)

    thumb = thumbnail(out, out_dir / f"{variation.key}.jpg", at=min(max(hook_end, 1.0) + 0.4, total / 2), width=540)
    return RenderOutput(video=out, thumb=thumb, duration=total, cue_count=cue_count,
                        broll_used=len(extras.broll), music_used=extras.music is not None,
                        motion_used=motion_used, motion_error=motion_error)
