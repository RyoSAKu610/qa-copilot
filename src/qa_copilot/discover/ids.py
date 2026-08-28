from __future__ import annotations

import hashlib


def listing_id(source: str, url_or_key: str) -> str:
    raw = f"{source}:{url_or_key}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]
