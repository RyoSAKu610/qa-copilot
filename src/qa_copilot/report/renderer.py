from __future__ import annotations

from qa_copilot.models import Listing, Qualification, RunReport
from qa_copilot.policy import get_source
from qa_copilot.store import Workspace


def render_report(
    ws: Workspace,
    listing: Listing,
    qual: Qualification | None,
    run: RunReport | None,
) -> str:
    policy = get_source(listing.source)
    lines = [
        f"# QA report — {listing.title}",
        "",
        "> **HUMAN REVIEW REQUIRED.** This is assistance, not a submission.",
        "> Do not paste this into a marketplace until you have verified every finding.",
        "",
        "## Job",
        "",
        f"- ID: `{listing.id}`",
        f"- Source: {policy.display_name} (`{listing.source}`)",
        f"- URL: {listing.url or '-'}",
        f"- Company: {listing.company or '-'}",
        f"- Access mode: `{policy.access.value}`",
        f"- Write mode: `{policy.write.value}`",
        f"- Client allows AI: {listing.client_allows_ai}",
        f"- AI disclosed: {listing.ai_disclosed}",
        f"- Test target: {listing.test_target or '-'}",
        "",
        "## Policy note",
        "",
        policy.ai_summary,
        "",
        policy.notes,
        "",
    ]
    if listing.attribution:
        lines += ["## Attribution", "", listing.attribution, ""]
    if qual:
        lines += [
            "## Qualification",
            "",
            f"- Verdict: **{qual.verdict}** (score {qual.score})",
            f"- Agent fit: {', '.join(qual.agent_fit) or '-'}",
            f"- Disqualifiers: {', '.join(qual.disqualifiers) or '-'}",
            "",
        ]
        for r in qual.reasons:
            lines.append(f"- {r}")
        lines.append("")
    if run:
        lines += ["## Findings", "", run.summary, ""]
        for i, f in enumerate(run.findings, 1):
            flag = "verified" if f.verified else "UNVERIFIED"
            lines += [
                f"### {i}. [{f.severity}] {f.title}",
                "",
                f"- Status: {flag}",
                f"- Detail: {f.detail}",
                f"- Evidence: {f.evidence or '-'}",
                "",
            ]
        if run.notes:
            lines += ["## Notes", ""]
            lines.extend(f"- {n}" for n in run.notes)
            lines.append("")
    lines += [
        "## Suggested next human steps",
        "",
        "1. Re-run any live check yourself.",
        "2. Mark each finding verified or drop it.",
        "3. If the marketplace requires AI disclosure, say so in your application.",
        "4. `qa-copilot approve` then `qa-copilot packet` — then submit **manually**.",
        "",
        "## AI disclosure template",
        "",
        "I used an assistant to draft a test plan and a QA report. Every step was",
        "reviewed by me. I did not auto-submit this application.",
        "",
    ]
    text = "\n".join(lines)
    ws.write_text(listing.id, "report.md", text)
    ws.save_json(listing.id, "stage.json", {"stage": "reported"})
    return text
