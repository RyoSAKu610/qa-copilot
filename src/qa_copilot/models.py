from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class Listing:
    id: str
    source: str
    title: str
    url: str = ""
    company: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    fetched_at: str = ""
    attribution: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    # paste / execute hints
    test_target: str = ""
    permission_to_test: bool = False
    client_allows_ai: str = "unknown"  # yes | no | unknown
    ai_disclosed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Listing":
        known = set(cls.__dataclass_fields__)
        payload = {k: v for k, v in data.items() if k in known}
        payload.setdefault("tags", [])
        payload.setdefault("extra", {})
        return cls(**payload)


@dataclass
class Qualification:
    listing_id: str
    score: int
    verdict: str  # candidate | reject | needs_human
    reasons: list[str]
    agent_fit: list[str]
    disqualifiers: list[str]
    qualified_at: str
    payout_usd: float | None = None
    payout_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Qualification":
        payout = data.get("payout_usd")
        return cls(
            listing_id=data["listing_id"],
            score=int(data["score"]),
            verdict=data["verdict"],
            reasons=list(data.get("reasons") or []),
            agent_fit=list(data.get("agent_fit") or []),
            disqualifiers=list(data.get("disqualifiers") or []),
            qualified_at=data.get("qualified_at") or utc_now(),
            payout_usd=float(payout) if payout is not None else None,
            payout_note=data.get("payout_note") or "",
        )


@dataclass
class Finding:
    severity: str  # blocker | major | minor | info
    title: str
    detail: str
    evidence: str = ""
    verified: bool = False


@dataclass
class RunReport:
    listing_id: str
    generated_at: str
    findings: list[Finding]
    summary: str
    evidence_dir: str
    unverified: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "evidence_dir": self.evidence_dir,
            "unverified": self.unverified,
            "notes": self.notes,
            "findings": [asdict(f) for f in self.findings],
        }
