"""Builds ASS subtitle files (word-chunked social captions + on-screen hook) for a cut."""

from dataclasses import dataclass

from app.media.plan import Variation

PLAY_W, PLAY_H = 1080, 1920
FONT = "Poppins"


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _ass_color(hex_color: str, alpha: str = "00") -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FF6A2B"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha}{b}{g}{r}".upper()


def _ts(t: float) -> str:
    t = max(t, 0)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def words_for_cut(transcripts: dict | list | None, variation: Variation) -> list[dict]:
    """Map transcript words onto the cut's own timeline (clips are concatenated).

    `transcripts` is one transcript (single source) or a list indexed like `Clip.source`.
    """
    if not transcripts:
        return []
    per_source = [transcripts] if isinstance(transcripts, dict) else list(transcripts)
    words_by_source = [
        [w for seg in (t or {}).get("segments", []) for w in seg.get("words", [])] for t in per_source
    ]
    out: list[dict] = []
    offset = 0.0
    for clip in variation.clips:
        words = words_by_source[clip.source] if clip.source < len(words_by_source) else []
        for w in words:
            ws, we = float(w["start"]), float(w["end"])
            if we <= clip.start or ws >= clip.end:
                continue
            out.append({
                "start": max(ws, clip.start) - clip.start + offset,
                "end": min(we, clip.end) - clip.start + offset,
                "word": str(w["word"]).strip(),
            })
        offset += clip.end - clip.start
    return [w for w in out if w["word"]]


def chunk_words(words: list[dict], max_words: int = 3, max_chars: int = 18, max_gap: float = 0.6) -> list[Cue]:
    cues: list[Cue] = []
    cur: list[dict] = []

    def flush() -> None:
        if cur:
            cues.append(Cue(cur[0]["start"], cur[-1]["end"], " ".join(w["word"] for w in cur)))
            cur.clear()

    for w in words:
        if cur:
            gap = w["start"] - cur[-1]["end"]
            text_len = len(" ".join(x["word"] for x in cur)) + 1 + len(w["word"])
            if len(cur) >= max_words or text_len > max_chars or gap > max_gap:
                flush()
        cur.append(w)
        if w["word"].endswith((".", "?", "!")):
            flush()
    flush()
    # Make cues contiguous so captions don't flicker between words
    for a, b in zip(cues, cues[1:], strict=False):
        if 0 < b.start - a.end < 0.35:
            a.end = b.start
    return cues


def build_ass(cues: list[Cue], hook_text: str, position: str, accent: str, total: float) -> str:
    margin_v = 520 if position == "center" else 260
    accent_c = _ass_color(accent)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {PLAY_W}",
        f"PlayResY: {PLAY_H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{FONT},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,6,2,2,80,80,{margin_v},1",
        f"Style: Hook,{FONT},66,&H000F1115,&H000F1115,{accent_c},{accent_c},"
        "-1,0,0,0,100,100,0,0,3,18,0,8,90,90,240,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if hook_text.strip():
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(min(3.0, total))},Hook,,0,0,0,,{_escape(hook_text.strip())}")
    for c in cues:
        text = _escape(c.text.upper())
        # Pop-in: start slightly larger, settle to 100%
        lines.append(
            f"Dialogue: 0,{_ts(c.start)},{_ts(c.end)},Caption,,0,0,0,,"
            f"{{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}}{text}"
        )
    return "\n".join(lines) + "\n"
