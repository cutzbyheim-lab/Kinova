"""The editing plan: structured, validated instructions the renderer executes.

The AI never produces FFmpeg commands. It produces this JSON, which is validated
and clamped against the real sources before anything is rendered.

A plan can draw from several source videos (`Clip.source` indexes them), place
stock B-roll cutaways on the cut's own timeline, and pick a music track.
"""

import re

from pydantic import BaseModel, Field, field_validator

MIN_CLIP_S = 0.8
MIN_TOTAL_S = 5.0
MAX_TOTAL_S = 90.0
MAX_CLIPS = 12
MAX_BROLL = 5
MIN_BROLL_S = 1.0
MAX_BROLL_S = 5.0


class PlanError(ValueError):
    pass


class Clip(BaseModel):
    source: int = Field(default=0, ge=0)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    # Where the subject sits horizontally (0 = left edge, 1 = right) — keeps them in the 9:16 crop.
    focus_x: float = Field(default=0.5, ge=0, le=1)
    # Punch-in: 1.0 = full frame, up to 1.35 = tight. Alternating zooms give jump cuts energy.
    zoom: float = Field(default=1.0, ge=1.0, le=1.35)


class BRoll(BaseModel):
    """A stock cutaway covering the picture while the original audio keeps playing."""

    at: float = Field(ge=0, description="seconds into the finished cut")
    duration: float = Field(gt=0)
    query: str = Field(min_length=2, max_length=80, description="what to search on Pexels")


class Music(BaseModel):
    track_id: str | None = None
    volume: float = Field(default=0.15, ge=0.02, le=0.6)


class Variation(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    style: str = Field(default="", max_length=60)
    title_idea: str = Field(default="", max_length=200)
    hook_text: str = Field(default="", max_length=80)
    reason: str = Field(default="", max_length=600)
    subtitle_position: str = "center"  # center | bottom
    cta_text: str = Field(default="", max_length=28)
    clips: list[Clip] = Field(min_length=1, max_length=MAX_CLIPS)
    broll: list[BRoll] = Field(default_factory=list, max_length=10)
    music: Music | None = None

    @field_validator("key")
    @classmethod
    def slug(cls, v: str) -> str:
        s = re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")
        return s or "variation"

    @field_validator("subtitle_position")
    @classmethod
    def pos(cls, v: str) -> str:
        return v if v in ("center", "bottom") else "center"

    @property
    def duration(self) -> float:
        return sum(c.end - c.start for c in self.clips)


class EditPlan(BaseModel):
    planner: str = "claude"
    summary: str = ""
    variations: list[Variation] = Field(min_length=1, max_length=5)


def _clean_broll(items: list[BRoll], total: float) -> list[BRoll]:
    out: list[BRoll] = []
    last_end = -1.0
    for b in sorted(items, key=lambda x: x.at):
        at = max(0.0, b.at)
        dur = min(max(b.duration, MIN_BROLL_S), MAX_BROLL_S)
        # never cover the first second (the hook) and stay inside the cut
        at = max(at, 1.0)
        if at + dur > total - 0.3:
            dur = total - 0.3 - at
        if dur < MIN_BROLL_S or at < last_end + 0.5:
            continue
        out.append(BRoll(at=round(at, 2), duration=round(dur, 2), query=b.query.strip()))
        last_end = at + dur
        if len(out) >= MAX_BROLL:
            break
    return out


def validate_plan(
    plan: EditPlan,
    source_durations: float | list[float],
    music_ids: set[str] | None = None,
) -> EditPlan:
    """Clamp clips to the real footage and reject plans that can't be rendered."""
    durations = [source_durations] if isinstance(source_durations, (int, float)) else list(source_durations)
    if not durations or max(durations) <= 0:
        raise PlanError("Source has no duration")
    seen: set[str] = set()
    cleaned: list[Variation] = []
    for var in plan.variations:
        clips: list[Clip] = []
        for c in var.clips:
            if c.source >= len(durations):
                continue
            dur = durations[c.source]
            start = max(0.0, min(c.start, dur))
            end = max(0.0, min(c.end, dur))
            if end - start >= MIN_CLIP_S:
                clips.append(c.model_copy(update={"start": round(start, 2), "end": round(end, 2)}))
        if not clips:
            continue
        total = sum(c.end - c.start for c in clips)
        while total > MAX_TOTAL_S and clips:
            over = total - MAX_TOTAL_S
            last = clips[-1]
            if last.end - last.start - over >= MIN_CLIP_S:
                clips[-1] = last.model_copy(update={"end": round(last.end - over, 2)})
            else:
                clips.pop()
            total = sum(c.end - c.start for c in clips)
        if total < min(MIN_TOTAL_S, sum(durations) * 0.9):
            continue
        music = var.music
        if music and music.track_id and (music_ids is None or music.track_id not in music_ids):
            music = None
        key = var.key
        n = 2
        while key in seen:
            key = f"{var.key}-{n}"
            n += 1
        seen.add(key)
        cleaned.append(var.model_copy(update={
            "clips": clips, "key": key, "broll": _clean_broll(var.broll, total), "music": music,
        }))
    if not cleaned:
        raise PlanError("No renderable variations in the plan")
    return plan.model_copy(update={"variations": cleaned})
