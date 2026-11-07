"""Marketing copy for each rendered clip (cheap model)."""

import json

from app.ai.llm import ClaudeLLM, extract_json

SYSTEM = """You are KINOVA's social copywriter. Write platform-native copy in the brand's voice.
Learn from the trending titles you are given (length, phrasing, hooks) and aim to beat them — never copy them.
No false claims, no invented facts about the footage. Output JSON only."""


def write_copy(
    llm: ClaudeLLM,
    variations: list[dict],
    transcript_excerpts: dict[str, str],
    trends: dict | None,
    brand: dict | None,
    platform: str,
    goal: str,
) -> dict[str, dict]:
    items = [
        {"key": v["key"], "style": v.get("style"), "title_idea": v.get("title_idea"),
         "what_is_said": transcript_excerpts.get(v["key"], "")[:1200]}
        for v in variations
    ]
    trend_bits = {
        k: trends.get(k) for k in ("top_keywords", "top_tags", "title_patterns", "median_title_chars")
    } if trends else None
    top_titles = [t["title"] for t in (trends or {}).get("top_videos", [])][:8]
    prompt = f"""PLATFORM: {platform}
GOAL: {goal or "grow reach and engagement"}
BRAND: {json.dumps(brand or {}, ensure_ascii=False)[:1500]}
TREND PATTERNS: {json.dumps(trend_bits) if trend_bits else "(unavailable)"}
TRENDING TITLES (for style reference only): {json.dumps(top_titles, ensure_ascii=False)}

CLIPS:
{json.dumps(items, ensure_ascii=False, indent=1)}

For each clip return: title (max 70 chars), hook (first line of the caption, max 12 words),
caption (2–4 short lines), hashtags (5–8, lowercase, with #), cta (one short line).
Return ONLY: {{"clips": [{{"key": "...", "title": "...", "hook": "...", "caption": "...", "hashtags": ["#..."], "cta": "..."}}]}}"""
    reply = llm.complete("marketing_copy", "fast", SYSTEM, prompt, max_tokens=3000)
    data = extract_json(reply.text)
    out: dict[str, dict] = {}
    for c in data.get("clips", []):
        if isinstance(c, dict) and c.get("key"):
            tags = [t if t.startswith("#") else f"#{t}" for t in c.get("hashtags", []) if isinstance(t, str)]
            out[c["key"]] = {
                "title": str(c.get("title", ""))[:300],
                "hook": str(c.get("hook", "")),
                "caption": str(c.get("caption", "")),
                "hashtags": tags[:10],
                "cta": str(c.get("cta", "")),
            }
    return out
