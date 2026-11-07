"""The editing plan: structured, validated instructions the renderer executes.

The AI never produces FFmpeg commands. It produces this JSON, which is validated
and clamped against the real source before anything is rendered.
"""

import re

from pydantic import BaseModel, Field, field_validator

MIN_CLIP_S = 0.8
MIN_TOTAL_S = 5.0
MAX_TOTAL_S = 90.0
MAX_CLIPS = 8


class PlanError(ValueError):
    pass


class Clip(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class Variation(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    style: str = Field(default="", max_length=60)
    title_idea: str = Field(default="", max_length=200)
    hook_text: str = Field(default="", max_length=80)
    reason: str = Field(default="", max_length=600)
    subtitle_position: str = "center"  # center | bottom
    clips: list[Clip] = Field(min_length=1, max_length=MAX_CLIPS)

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


def validate_plan(plan: EditPlan, source_duration: float) -> EditPlan:
    """Clamp clips to the real footage and reject plans that can't be rendered."""
    if source_duration <= 0:
        raise PlanError("Source has no duration")
    seen: set[str] = set()
    cleaned: list[Variation] = []
    for var in plan.variations:
        clips: list[Clip] = []
        for c in var.clips:
            start = max(0.0, min(c.start, source_duration))
            end = max(0.0, min(c.end, source_duration))
            if end - start >= MIN_CLIP_S:
                clips.append(Clip(start=round(start, 2), end=round(end, 2)))
        if not clips:
            continue
        # Trim from the end if the cut is too long
        total = sum(c.end - c.start for c in clips)
        while total > MAX_TOTAL_S and clips:
            over = total - MAX_TOTAL_S
            last = clips[-1]
            if last.end - last.start - over >= MIN_CLIP_S:
                clips[-1] = Clip(start=last.start, end=round(last.end - over, 2))
            else:
                clips.pop()
            total = sum(c.end - c.start for c in clips)
        if total < min(MIN_TOTAL_S, source_duration * 0.9):
            continue
        key = var.key
        n = 2
        while key in seen:
            key = f"{var.key}-{n}"
            n += 1
        seen.add(key)
        cleaned.append(var.model_copy(update={"clips": clips, "key": key}))
    if not cleaned:
        raise PlanError("No renderable variations in the plan")
    return plan.model_copy(update={"variations": cleaned})
