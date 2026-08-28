from __future__ import annotations

from pathlib import Path

import yaml

from qa_copilot.models import Listing, utc_now
from qa_copilot.policy import PolicyError, get_source
from qa_copilot.redact import redact

from .ids import listing_id

FRONT_KEYS = {
    "source",
    "title",
    "url",
    "company",
    "test_target",
    "permission_to_test",
    "client_allows_ai",
    "ai_disclosed",
    "tags",
}


def parse_paste(path: Path) -> Listing:
    raw = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            loaded = yaml.safe_load(parts[1]) or {}
            if not isinstance(loaded, dict):
                raise PolicyError(f"{path}: YAML front matter must be a mapping")
            meta = loaded
            body = parts[2].lstrip("\n")

    source = str(meta.get("source") or "paste")
    policy = get_source(source) if source != "paste" else get_source("paste")
    if policy.access.value == "disabled":
        raise PolicyError(f"{source} is disabled. Do not ingest it even as paste.")
    if policy.access.value == "official_api" and source != "paste":
        # Allow tagging a paste with a marketplace name only when that name is paste_only.
        source = "paste"

    title = str(meta.get("title") or path.stem)
    url = str(meta.get("url") or f"paste://{path.name}")
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return Listing(
        id=listing_id(source, f"{path.resolve()}::{title}"),
        source=source,
        title=title,
        url=url,
        company=str(meta.get("company") or ""),
        description=redact(body),
        tags=list(tags),
        fetched_at=utc_now(),
        test_target=str(meta.get("test_target") or ""),
        permission_to_test=bool(meta.get("permission_to_test", False)),
        client_allows_ai=str(meta.get("client_allows_ai") or "unknown"),
        ai_disclosed=bool(meta.get("ai_disclosed", False)),
        extra={"paste_path": str(path), "unused_keys": [k for k in meta if k not in FRONT_KEYS]},
    )
