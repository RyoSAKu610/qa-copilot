from __future__ import annotations

from qa_copilot.models import Listing, utc_now
from qa_copilot.policy import PolicyError, assert_write_allowed, get_source
from qa_copilot.store import Workspace

CHECKLIST = (
    "i_read_the_report",
    "i_verified_or_dropped_unverified_findings",
    "i_accept_the_target_platform_terms",
    "i_will_submit_manually",
    "i_will_disclose_ai_if_required",
)


def approve(ws: Workspace, listing: Listing, operator: str, checks: dict[str, bool]) -> None:
    missing = [k for k in CHECKLIST if not checks.get(k)]
    if missing:
        raise PolicyError("approval refused; set all checklist flags:\n- " + "\n- ".join(missing))
    if not operator.strip():
        raise PolicyError("operator name is required — a human has to own this")
    ws.save_json(
        listing.id,
        "approval.json",
        {
            "approved": True,
            "operator": operator.strip(),
            "approved_at": utc_now(),
            "listing_id": listing.id,
            "source": listing.source,
            "checks": {k: True for k in CHECKLIST},
        },
    )
    ws.save_json(listing.id, "stage.json", {"stage": "approved"})


def build_packet(ws: Workspace, listing: Listing) -> str:
    if not ws.is_approved(listing.id):
        raise PolicyError("refusing packet: run `qa-copilot approve` first")
    assert_write_allowed(listing.source, approved=True)
    policy = get_source(listing.source)
    report = ws.job_dir(listing.id) / "report.md"
    report_text = report.read_text(encoding="utf-8") if report.exists() else "(no report.md)"
    packet = "\n".join(
        [
            "# Manual submission packet",
            "",
            "This file is for a human to copy from. qa-copilot does not send it anywhere.",
            "",
            f"- Listing: {listing.title}",
            f"- Source: {policy.display_name}",
            f"- Open this URL yourself: {listing.url or '(paste/local)'}",
            "",
            "## Suggested message",
            "",
            f"Hello, I reviewed `{listing.title}` and prepared a QA plan/report.",
            "I will not auto-bid. If useful I can share a short test plan and reproduce steps.",
            "I used an assistant for drafting; I verified the contents.",
            "",
            "## Do not",
            "",
            "- Do not run a bot against the marketplace UI.",
            "- Do not submit unverified findings to bug-bounty platforms.",
            "- Do not test production URLs without written permission.",
            "",
            "## Attached report",
            "",
            report_text,
            "",
        ]
    )
    path = ws.write_text(listing.id, "packet/APPLY.md", packet)
    ws.save_json(listing.id, "stage.json", {"stage": "packet"})
    return str(path)
