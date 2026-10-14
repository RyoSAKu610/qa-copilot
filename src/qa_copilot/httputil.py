from __future__ import annotations

import time
from collections import defaultdict

import httpx

from .policy import PolicyError, assert_http_allowed

USER_AGENT = (
    "qa-copilot/0.1 (+https://github.com/RyoSAKu610/qa-copilot; "
    "official-API-only; human-gated; no-scrape-marketplaces)"
)
MIN_INTERVAL_SEC = 2.0
_last_host: dict[str, float] = defaultdict(float)


def _pace(host: str) -> None:
    now = time.monotonic()
    wait = MIN_INTERVAL_SEC - (now - _last_host[host])
    if wait > 0:
        time.sleep(wait)
    _last_host[host] = time.monotonic()


def get_json(source_id: str, url: str, *, headers: dict[str, str] | None = None, timeout: float = 30.0) -> object:
    assert_http_allowed(source_id, url)
    host = httpx.URL(url).host
    _pace(host)
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged.update(headers)
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=merged) as client:
        resp = client.get(url)
        if resp.status_code == 429:
            raise PolicyError(f"{source_id}: rate limited (HTTP 429). Slow down and retry later.")
        if resp.status_code in (401, 403):
            raise PolicyError(
                f"{source_id}: access denied (HTTP {resp.status_code}). "
                "This source needs its own credentials (see `qa-copilot policy`) or is throttling; "
                "do not try to work around it."
            )
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "json" not in ctype and not resp.text.lstrip().startswith(("{", "[")):
            raise PolicyError(f"{source_id}: expected JSON from {url}, got {ctype!r}")
        return resp.json()


def post_json(
    source_id: str,
    url: str,
    payload: object,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> object:
    """POST a JSON body to an allowlisted host and parse the JSON reply.

    Only the official Apify run endpoint uses this today. The timeout is long
    because a hosted actor can take a while to run.
    """
    assert_http_allowed(source_id, url)
    host = httpx.URL(url).host
    _pace(host)
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        merged.update(headers)
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=merged) as client:
        resp = client.post(url, json=payload)
        if resp.status_code == 429:
            raise PolicyError(f"{source_id}: rate limited (HTTP 429). Slow down and retry later.")
        if resp.status_code in (401, 403):
            raise PolicyError(
                f"{source_id}: access denied (HTTP {resp.status_code}). "
                "This source needs its own credentials (see `qa-copilot policy`) or is throttling; "
                "do not try to work around it."
            )
        if resp.status_code >= 400:
            # Apify puts a human-readable message in the body; surface it.
            raise PolicyError(f"{source_id}: HTTP {resp.status_code} from {host}: {resp.text[:300]}")
        ctype = resp.headers.get("content-type", "")
        if "json" not in ctype and not resp.text.lstrip().startswith(("{", "[")):
            raise PolicyError(f"{source_id}: expected JSON from {url}, got {ctype!r}")
        return resp.json()


def get_text(source_id: str, url: str, *, timeout: float = 30.0) -> httpx.Response:
    """Fetch a URL that the policy already allowlisted (test targets use a different helper)."""
    assert_http_allowed(source_id, url)
    host = httpx.URL(url).host
    _pace(host)
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp
