"""Stock B-roll from Pexels (free for commercial use; credit Pexels and the creator).

API: https://www.pexels.com/api/documentation/ — 200 requests/hour, 20,000/month by default.
"""

from dataclasses import dataclass
from pathlib import Path

import httpx

from app.ai.llm import NotConfigured
from app.core.config import get_settings

API = "https://api.pexels.com/v1/videos/search"
MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024


@dataclass
class StockClip:
    provider: str
    id: str
    page_url: str
    author: str
    author_url: str
    file_url: str
    width: int
    height: int
    duration: float

    def credit(self) -> dict:
        return {"provider": self.provider, "id": self.id, "page_url": self.page_url,
                "author": self.author, "author_url": self.author_url}


def _best_file(files: list[dict]) -> dict | None:
    mp4 = [f for f in files if f.get("file_type") == "video/mp4" and f.get("link") and f.get("height")]
    if not mp4:
        return None
    # Prefer portrait files at or below 1920px tall, as large as possible (sharp but not 4K-heavy)
    under = [f for f in mp4 if f["height"] <= 1920]
    pool = under or mp4
    return max(pool, key=lambda f: (f["height"] >= f.get("width", 0), f["height"]))


def search_pexels(query: str, min_duration: float = 3, client: httpx.Client | None = None) -> StockClip | None:
    s = get_settings()
    if not s.pexels_configured:
        raise NotConfigured("PEXELS_API_KEY is not set")
    own = client is None
    client = client or httpx.Client(timeout=20)
    try:
        r = client.get(API, params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 8},
                       headers={"Authorization": s.pexels_api_key})
        r.raise_for_status()
        for v in r.json().get("videos", []):
            if float(v.get("duration") or 0) < min_duration:
                continue
            f = _best_file(v.get("video_files", []))
            if not f:
                continue
            user = v.get("user") or {}
            return StockClip(
                provider="pexels", id=str(v["id"]), page_url=v.get("url", ""),
                author=user.get("name", ""), author_url=user.get("url", ""),
                file_url=f["link"], width=int(f.get("width") or 0), height=int(f["height"]),
                duration=float(v.get("duration") or 0),
            )
        return None
    finally:
        if own:
            client.close()


def download(url: str, dest: Path, client: httpx.Client | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    own = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            size = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1024 * 256):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise ValueError("Stock clip is too large")
                    f.write(chunk)
        tmp.replace(dest)
        return dest
    finally:
        tmp.unlink(missing_ok=True)
        if own:
            client.close()
