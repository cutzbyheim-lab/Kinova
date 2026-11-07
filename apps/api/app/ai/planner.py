"""Turns transcript + trends + brand into a validated EditPlan.

Two planners:
- Claude (default when configured): reads the transcript and trend patterns and decides cuts.
- Heuristic (fallback, NOT AI): picks speech-dense windows. Clearly labelled in the UI.
"""

import json

from app.ai.llm import ClaudeLLM, extract_json
from app.media.plan import EditPlan, PlanError, validate_plan

STYLE_LIBRARY = {
    "hook": "Attention-grabbing: open on the single most surprising or bold line; 15–30s; no slow intro.",
    "story": "Storytelling: setup → tension → payoff in chronological order; 30–60s.",
    "fast": "Fast-paced social: 3–5 punchy fragments stitched together, each 3–8s; 15–25s total.",
    "educational": "Educational: one clear takeaway explained simply; 30–60s.",
    "promo": "Promotional: lead with the benefit, end on a call to action; 15–30s.",
}
DEFAULT_STYLES = ["hook", "story", "fast", "educational", "promo"]

SYSTEM = """You are KINOVA's senior short-form video editor.
You receive a timestamped transcript of raw footage, trend data from YouTube for the topic, and the brand profile.
You output an editing plan as JSON only. You can only use footage that exists: every clip must lie within the
source duration, and you must choose timestamps that start and end on natural speech boundaries
(use the segment timestamps). Never invent content. Variations must make genuinely different editing decisions
(different moments, order, pacing, length), not just different captions.
Use the trend data to choose lengths, hook style and pacing that match or beat what is performing now."""


def _transcript_lines(transcript: dict | None, max_chars: int = 14000) -> str:
    if not transcript or not transcript.get("segments"):
        return "(no speech detected — plan from timing alone, keep cuts evenly spaced)"
    lines, total = [], 0
    for seg in transcript["segments"]:
        line = f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}"
        total += len(line) + 1
        if total > max_chars:
            lines.append("[… transcript truncated …]")
            break
        lines.append(line)
    return "\n".join(lines)


def _brand_block(brand: dict | None) -> str:
    if not brand:
        return "(no brand selected)"
    keys = ["name", "industry", "audience", "voice", "personality", "goals", "editing_style", "instructions"]
    return "\n".join(f"{k}: {brand[k]}" for k in keys if brand.get(k))


def claude_plan(
    llm: ClaudeLLM,
    duration: float,
    transcript: dict | None,
    trends: dict | None,
    brand: dict | None,
    goal: str,
    platform: str,
    n: int,
) -> EditPlan:
    styles = DEFAULT_STYLES[:n]
    style_text = "\n".join(f"- {s}: {STYLE_LIBRARY[s]}" for s in styles)
    prompt = f"""SOURCE DURATION: {duration:.1f} seconds
TARGET PLATFORM: {platform} (vertical 9:16)
USER GOAL: {goal or "(none given — make the most engaging clips possible)"}

BRAND PROFILE:
{_brand_block(brand)}

YOUTUBE TREND PATTERNS FOR THIS TOPIC:
{json.dumps(trends, indent=1) if trends else "(trend data unavailable)"}

TRANSCRIPT:
{_transcript_lines(transcript)}

Make exactly {n} variations, one per style:
{style_text}

Return ONLY this JSON:
{{
  "summary": "one sentence on what the footage is about and the strongest moments",
  "variations": [
    {{
      "key": "<style name>",
      "style": "<style name>",
      "title_idea": "<working title, max 70 chars>",
      "hook_text": "<on-screen text for the first 3 seconds, max 6 words, or empty>",
      "subtitle_position": "center",
      "reason": "<why these moments, referencing the trend data where relevant>",
      "clips": [{{"start": <seconds>, "end": <seconds>}}]
    }}
  ]
}}"""
    reply = llm.complete("edit_plan", "smart", SYSTEM, prompt, max_tokens=8000)
    try:
        data = extract_json(reply.text)
        plan = EditPlan(planner="claude", summary=data.get("summary", ""), variations=data["variations"])
        return validate_plan(plan, duration)
    except (ValueError, KeyError, PlanError) as first_error:
        # One repair attempt, feeding the validation error back
        fix = llm.complete(
            "edit_plan_repair", "smart", SYSTEM,
            prompt + f"\n\nYour previous answer was invalid ({first_error}). Return corrected JSON only.",
            max_tokens=6000,
        )
        data = extract_json(fix.text)
        plan = EditPlan(planner="claude", summary=data.get("summary", ""), variations=data["variations"])
        return validate_plan(plan, duration)


def heuristic_plan(duration: float, transcript: dict | None, n: int, reason: str) -> EditPlan:
    """Deterministic, non-AI fallback so the pipeline still produces something reviewable."""
    segs = (transcript or {}).get("segments") or []
    variations = []

    def window(start: float, length: float) -> dict:
        s = max(0.0, min(start, max(duration - length, 0)))
        return {"start": round(s, 2), "end": round(min(s + length, duration), 2)}

    def density(seg: dict) -> float:
        d = max(seg["end"] - seg["start"], 0.5)
        return len(seg.get("words") or seg["text"].split()) / d

    if segs:
        ranked = sorted(segs, key=density, reverse=True)
        best = ranked[0]
        variations.append({"key": "hook", "style": "hook", "hook_text": "",
                           "clips": [window(best["start"], 22)]})
        variations.append({"key": "story", "style": "story", "hook_text": "",
                           "clips": [window(segs[0]["start"], 45)]})
        fast = sorted(ranked[:4], key=lambda s: s["start"])
        variations.append({"key": "fast", "style": "fast", "hook_text": "",
                           "clips": [{"start": s["start"], "end": min(s["end"], s["start"] + 6)} for s in fast]})
    else:
        spots = [duration * f for f in (0.1, 0.4, 0.7)]
        variations.append({"key": "hook", "style": "hook", "hook_text": "", "clips": [window(spots[0], 20)]})
        variations.append({"key": "story", "style": "story", "hook_text": "", "clips": [window(0, 40)]})
        variations.append({"key": "fast", "style": "fast", "hook_text": "",
                           "clips": [window(t, 5) for t in spots]})
    for v in variations:
        v["reason"] = "Heuristic pick (speech density / spacing) — not AI."
    plan = EditPlan(planner="heuristic", summary=reason, variations=variations[: max(1, min(n, 3))])
    return validate_plan(plan, duration)
