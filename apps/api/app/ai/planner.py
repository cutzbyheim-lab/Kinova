"""Turns transcripts + trends + brand (+ music library) into a validated EditPlan.

Two planners:
- Claude (default when configured): reads every source's transcript and the trend patterns,
  decides cuts across all clips, places stock B-roll and picks music.
- Heuristic (fallback, NOT AI): picks speech-dense windows. Clearly labelled in the UI.
"""

import json

from app.ai.llm import ClaudeLLM, extract_json
from app.media.plan import EditPlan, PlanError, validate_plan

STYLE_LIBRARY = {
    "hook": "Attention-grabbing: open on the single most surprising or bold line; 15–30s; no slow intro.",
    "story": "Storytelling: setup → tension → payoff in chronological order; 30–60s.",
    "fast": "Fast-paced social: 3–6 punchy fragments stitched together, each 2–6s; 15–25s total.",
    "educational": "Educational: one clear takeaway explained simply; 30–60s.",
    "promo": "Promotional: lead with the benefit, end on a call to action; 15–30s.",
}
DEFAULT_STYLES = ["hook", "story", "fast", "educational", "promo"]

SYSTEM = """You are KINOVA's senior short-form video editor.
You receive timestamped transcripts of one or more raw source clips, YouTube trend data for the topic,
the brand profile, and optionally a music library. You output an editing plan as JSON only.

Rules:
- Only use footage that exists: each clip names its `source` index and lies within that source's duration.
- When there are several sources, build the best possible video from ALL of them: combine the strongest
  moments across clips, intercut where it helps the story, and do not ignore a source without a reason.
- Variations must make genuinely different editing decisions (moments, order, pacing, length), not just
  different captions.
- Use the trend data to choose lengths, hook style and pacing that match or beat what is performing now.
- Never invent content.

Editing craft (what separates a pro short from an amateur one):
- The first 1.5s decides everything: open on the boldest line or the most striking visual, never on a greeting,
  a breath or a setup.
- Cut tight. Start each clip right as speech starts and end ~0.1s after the last word; cut out "um",
  false starts, repeats and dead air by splitting into more, shorter clips. Use word timestamps, not just segments.
- Structure: HOOK → context (one line) → 2–4 beats → payoff (the result, the reveal, the before/after) → CTA.
- Visual moments matter as much as quotes: for hands-on work (a haircut, a product, a process) include the
  satisfying visual beats — the transformation, the finished result, close-ups of the craft.

You may receive CONTACT SHEETS: frames sampled from the footage, each tile stamped "S<source> HH:MM:SS.mmm".
Use them to (1) find visually strong moments, (2) set each clip's `focus_x` to where the main subject sits
horizontally (0 = left edge, 0.5 = center, 1 = right edge) so the vertical 9:16 crop keeps them in frame, and
(3) choose `zoom` (1.0–1.25): alternate e.g. 1.0 / 1.15 between consecutive clips of the same shot so jump
cuts feel intentional; keep 1.0 on wide shots where the action fills the frame."""

BROLL_RULES = """B-ROLL (stock cutaways from Pexels, shown over the picture while the original audio continues):
- Add 0–4 per variation, only where a visual illustrates what is being said (a product, a place, an action).
- `at` is seconds into the FINISHED cut (after concatenating clips), `duration` 1.5–4s.
- Never during the first 1.5s (the hook) and not over someone's key on-camera moment.
- `query` is 1–4 concrete visual English words that stock footage would match, e.g. "barber clippers close up"."""

NO_BROLL = "B-ROLL: not available for this production — return an empty `broll` list."


def _transcript_lines(transcript: dict | None, max_chars: int) -> str:
    """Segments with word-level timestamps, e.g. `[3.2-6.8] so(3.2) here's(3.5) the(3.7) trick(3.9)`."""
    if not transcript or not transcript.get("segments"):
        return "(no speech detected — choose moments by timing and the contact sheets)"
    lines, total = [], 0
    for seg in transcript["segments"]:
        words = seg.get("words") or []
        body = " ".join(f"{w['word']}({w['start']:.1f})" for w in words) if words else seg["text"]
        line = f"[{seg['start']:.1f}-{seg['end']:.1f}] {body}"
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


def _sources_block(sources: list[dict], transcripts: list[dict | None]) -> str:
    budget = max(6000, 40000 // max(len(sources), 1))  # word timings ≈ 3× the text; ~12k tokens max
    blocks = []
    for i, s in enumerate(sources):
        t = transcripts[i] if i < len(transcripts) else None
        blocks.append(f"--- SOURCE {i}: {s.get('filename', f'clip {i}')} · {s['duration']:.1f}s ---\n"
                      + _transcript_lines(t, budget))
    return "\n\n".join(blocks)


def claude_plan(
    llm: ClaudeLLM,
    sources: list[dict],
    transcripts: list[dict | None],
    trends: dict | None,
    brand: dict | None,
    goal: str,
    platform: str,
    n: int,
    music_library: list[dict] | None = None,
    allow_broll: bool = False,
    sheets: list[bytes] | None = None,
    sheet_step: float | None = None,
) -> EditPlan:
    styles = DEFAULT_STYLES[:n]
    sheets = sheets or []
    sheet_note = (
        f"CONTACT SHEETS: {len(sheets)} image(s) above, one frame every {sheet_step:.1f}s per source, in source order."
        if sheets else "CONTACT SHEETS: none (plan from the transcripts)."
    )
    style_text = "\n".join(f"- {s}: {STYLE_LIBRARY[s]}" for s in styles)
    music_library = music_library or []
    music_text = (
        "MUSIC LIBRARY (licensed tracks you may use; pick the best fit per variation by mood, or null for none):\n"
        + json.dumps(music_library, ensure_ascii=False)
        + "\nMusic plays quietly under the voice and ducks automatically; `volume` 0.08–0.25 (lower for talky cuts)."
        if music_library else "MUSIC: none available — set `music` to null."
    )
    prompt = f"""TARGET PLATFORM: {platform} (vertical 9:16)
USER GOAL: {goal or "(none given — make the most engaging clips possible)"}

BRAND PROFILE:
{_brand_block(brand)}

YOUTUBE TREND PATTERNS FOR THIS TOPIC:
{json.dumps(trends, indent=1) if trends else "(trend data unavailable)"}

SOURCES ({len(sources)}):
{_sources_block(sources, transcripts)}

{sheet_note}

{BROLL_RULES if allow_broll else NO_BROLL}

{music_text}

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
      "cta_text": "<on-screen call to action, 2–4 words from the brand goals/goal, e.g. 'Book your cut', or empty>",
      "reason": "<why these moments, referencing what you saw and the trend data>",
      "clips": [{{"source": <index>, "start": <seconds>, "end": <seconds>, "focus_x": <0–1>, "zoom": <1.0–1.25>}}],
      "broll": [{{"at": <seconds into cut>, "duration": <seconds>, "query": "<stock search>"}}],
      "music": {{"track_id": "<id from library>", "volume": 0.15}} or null
    }}
  ]
}}"""
    durations = [s["duration"] for s in sources]
    music_ids = {m["id"] for m in music_library}

    def parse(text: str) -> EditPlan:
        data = extract_json(text)
        plan = EditPlan(planner="claude", summary=data.get("summary", ""), variations=data["variations"])
        plan = validate_plan(plan, durations, music_ids)
        if not allow_broll:
            plan = plan.model_copy(update={"variations": [v.model_copy(update={"broll": []}) for v in plan.variations]})
        return plan

    reply = llm.complete("edit_plan", "smart", SYSTEM, prompt, max_tokens=9000, images=sheets)
    try:
        return parse(reply.text)
    except (ValueError, KeyError, PlanError) as first_error:
        fix = llm.complete(
            "edit_plan_repair", "smart", SYSTEM,
            prompt + f"\n\nYour previous answer was invalid ({first_error}). Return corrected JSON only.",
            max_tokens=7000, images=sheets,
        )
        return parse(fix.text)


def heuristic_plan(
    durations: float | list[float],
    transcripts: dict | list | None,
    n: int,
    reason: str,
    music_library: list[dict] | None = None,
) -> EditPlan:
    """Deterministic, non-AI fallback so the pipeline still produces something reviewable."""
    durs = [durations] if isinstance(durations, (int, float)) else list(durations)
    trs = [transcripts] if isinstance(transcripts, dict) or transcripts is None else list(transcripts)
    trs = (trs + [None] * len(durs))[: len(durs)]

    def window(src: int, start: float, length: float) -> dict:
        d = durs[src]
        s = max(0.0, min(start, max(d - length, 0)))
        return {"source": src, "start": round(s, 2), "end": round(min(s + length, d), 2)}

    def density(seg: dict) -> float:
        return len(seg.get("words") or seg["text"].split()) / max(seg["end"] - seg["start"], 0.5)

    segs = [(i, seg) for i, t in enumerate(trs) for seg in ((t or {}).get("segments") or [])]
    variations = []
    if segs:
        ranked = sorted(segs, key=lambda x: density(x[1]), reverse=True)
        bi, best = ranked[0]
        variations.append({"key": "hook", "style": "hook", "clips": [window(bi, best["start"], 22)]})
        # story: opening of each source, in order
        per = max(8.0, 45.0 / len(durs))
        variations.append({"key": "story", "style": "story",
                           "clips": [window(i, 0, per) for i in range(len(durs))]})
        fast = sorted(ranked[:5], key=lambda x: (x[0], x[1]["start"]))
        variations.append({"key": "fast", "style": "fast", "clips": [
            {"source": i, "start": s["start"], "end": min(s["end"], s["start"] + 5)} for i, s in fast]})
    else:
        variations.append({"key": "hook", "style": "hook", "clips": [window(0, durs[0] * 0.1, 20)]})
        per = max(8.0, 40.0 / len(durs))
        variations.append({"key": "story", "style": "story", "clips": [window(i, 0, per) for i in range(len(durs))]})
        variations.append({"key": "fast", "style": "fast", "clips": [
            window(i, durs[i] * f, 4) for i in range(len(durs)) for f in (0.2, 0.6)][:6]})
    music = None
    if music_library:
        music = {"track_id": music_library[0]["id"], "volume": 0.14}
    for v in variations:
        v["reason"] = "Heuristic pick (speech density / spacing) — not AI."
        v["hook_text"] = ""
        v["music"] = music
        for k, c in enumerate(v["clips"]):  # alternate punch-ins so jump cuts read as intentional
            c["zoom"] = 1.12 if k % 2 else 1.0
    plan = EditPlan(planner="heuristic", summary=reason, variations=variations[: max(1, min(n, 3))])
    return validate_plan(plan, durs, {m["id"] for m in music_library or []})
