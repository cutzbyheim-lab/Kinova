"""YouTube trend research via the official YouTube Data API v3.

Finds the most-viewed recent videos for a topic and distils patterns the planner
can use: typical length, share of Shorts, title styles, recurring tags.
Costs: search.list = 100 quota units, videos.list = 1 unit (free quota: 10,000/day).
"""

import re
import statistics
from collections import Counter
from datetime import UTC, datetime, timedelta

import httpx

from app.ai.llm import NotConfigured
from app.core.config import get_settings

API = "https://www.googleapis.com/youtube/v3"
STOPWORDS = set(
    "the a an and or of to in on for with is are was be my your you i we it this that how what why when "
    "at by from as vs our me do does did not no yes so just can will get got new best top".split()
)


def _iso_duration_s(d: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    days, h, mi, s = (int(x or 0) for x in m.groups())
    return days * 86400 + h * 3600 + mi * 60 + s


def fetch_trending(topic: str, days: int = 30, limit: int = 25, client: httpx.Client | None = None) -> list[dict]:
    s = get_settings()
    if not s.youtube_configured:
        raise NotConfigured("YOUTUBE_API_KEY is not set")
    after = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    own = client is None
    client = client or httpx.Client(timeout=20)
    try:
        r = client.get(f"{API}/search", params={
            "key": s.youtube_api_key, "part": "snippet", "q": topic, "type": "video",
            "order": "viewCount", "publishedAfter": after, "maxResults": limit,
            "regionCode": s.youtube_region, "safeSearch": "moderate",
        })
        r.raise_for_status()
        ids = [it["id"]["videoId"] for it in r.json().get("items", []) if it.get("id", {}).get("videoId")]
        if not ids:
            return []
        r = client.get(f"{API}/videos", params={
            "key": s.youtube_api_key, "part": "snippet,contentDetails,statistics", "id": ",".join(ids),
        })
        r.raise_for_status()
        videos = []
        for it in r.json().get("items", []):
            sn, st = it.get("snippet", {}), it.get("statistics", {})
            videos.append({
                "id": it["id"],
                "title": sn.get("title", ""),
                "channel": sn.get("channelTitle", ""),
                "published_at": sn.get("publishedAt"),
                "tags": sn.get("tags", [])[:15],
                "duration_s": _iso_duration_s(it.get("contentDetails", {}).get("duration", "")),
                "views": int(st.get("viewCount", 0) or 0),
                "likes": int(st.get("likeCount", 0) or 0),
                "comments": int(st.get("commentCount", 0) or 0),
            })
        videos.sort(key=lambda v: v["views"], reverse=True)
        return videos
    finally:
        if own:
            client.close()


def summarize(topic: str, videos: list[dict]) -> dict:
    """Turn raw video data into patterns. Pure function — no network."""
    if not videos:
        return {"topic": topic, "sample_size": 0, "note": "No recent videos found for this topic."}
    durs = [v["duration_s"] for v in videos if v["duration_s"] > 0]
    shorts = [v for v in videos if 0 < v["duration_s"] <= 60]
    titles = [v["title"] for v in videos]
    words = Counter(
        w for t in titles for w in re.findall(r"[a-z0-9']+", t.lower()) if w not in STOPWORDS and len(w) > 2
    )
    tags = Counter(t.lower() for v in videos for t in v.get("tags", []))
    engagement = [
        (v["likes"] + v["comments"]) / v["views"] for v in videos if v["views"] > 0
    ]
    return {
        "topic": topic,
        "sample_size": len(videos),
        "window_days": 30,
        "median_duration_s": int(statistics.median(durs)) if durs else None,
        "shorts_share": round(len(shorts) / len(videos), 2),
        "median_short_duration_s": int(statistics.median([v["duration_s"] for v in shorts])) if shorts else None,
        "title_patterns": {
            "question_share": round(sum("?" in t for t in titles) / len(titles), 2),
            "number_share": round(sum(bool(re.search(r"\d", t)) for t in titles) / len(titles), 2),
            "allcaps_word_share": round(sum(bool(re.search(r"\b[A-Z]{3,}\b", t)) for t in titles) / len(titles), 2),
            "median_title_chars": int(statistics.median(len(t) for t in titles)),
        },
        "top_keywords": [w for w, _ in words.most_common(12)],
        "top_tags": [t for t, _ in tags.most_common(12)],
        "median_engagement_rate": round(statistics.median(engagement), 4) if engagement else None,
        "top_videos": [
            {k: v[k] for k in ("title", "channel", "views", "duration_s")} for v in videos[:8]
        ],
    }
