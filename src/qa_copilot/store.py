from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Listing, Qualification, utc_now


def default_root(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()) / ".qa-copilot"


class Workspace:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_root()
        self.listings_dir = self.root / "listings"
        self.jobs_dir = self.root / "jobs"
        self.inbox_dir = self.root / "inbox"
        self.root.mkdir(parents=True, exist_ok=True)
        self.listings_dir.mkdir(exist_ok=True)
        self.jobs_dir.mkdir(exist_ok=True)
        self.inbox_dir.mkdir(exist_ok=True)

    def listing_path(self, listing_id: str) -> Path:
        return self.listings_dir / f"{listing_id}.json"

    def job_dir(self, listing_id: str) -> Path:
        path = self.jobs_dir / listing_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_listing(self, listing: Listing) -> Path:
        path = self.listing_path(listing.id)
        data = listing.to_dict()
        if not data.get("fetched_at"):
            data["fetched_at"] = utc_now()
            listing.fetched_at = data["fetched_at"]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_listing(self, listing_id: str) -> Listing:
        path = self.listing_path(listing_id)
        if not path.exists():
            raise FileNotFoundError(f"listing not found: {listing_id}")
        return Listing.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def iter_listings(self) -> list[Listing]:
        items: list[Listing] = []
        for path in sorted(self.listings_dir.glob("*.json")):
            items.append(Listing.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return items

    def save_qualification(self, qual: Qualification) -> Path:
        path = self.job_dir(qual.listing_id) / "qualification.json"
        path.write_text(json.dumps(qual.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_qualification(self, listing_id: str) -> Qualification | None:
        path = self.job_dir(listing_id) / "qualification.json"
        if not path.exists():
            return None
        return Qualification.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_json(self, listing_id: str, name: str, data: Any) -> Path:
        path = self.job_dir(listing_id) / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_json(self, listing_id: str, name: str) -> Any | None:
        path = self.job_dir(listing_id) / name
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write_text(self, listing_id: str, name: str, text: str) -> Path:
        path = self.job_dir(listing_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def is_approved(self, listing_id: str) -> bool:
        data = self.load_json(listing_id, "approval.json")
        return bool(data and data.get("approved") is True)
