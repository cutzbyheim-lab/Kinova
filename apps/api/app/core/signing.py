"""HMAC-signed, expiring links for private media files."""

import hashlib
import hmac
import time
from urllib.parse import quote

from app.core.config import get_settings


def _sig(key: str, exp: int) -> str:
    secret = get_settings().secret_key.encode()
    return hmac.new(secret, f"{key}:{exp}".encode(), hashlib.sha256).hexdigest()


def signed_url(key: str | None, ttl: int | None = None, download: bool = False) -> str | None:
    if not key:
        return None
    exp = int(time.time()) + (ttl or get_settings().signed_url_ttl_seconds)
    url = f"/api/files/{quote(key)}?exp={exp}&sig={_sig(key, exp)}"
    return url + "&dl=1" if download else url


def verify(key: str, exp: int, sig: str) -> bool:
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(_sig(key, exp), sig)
