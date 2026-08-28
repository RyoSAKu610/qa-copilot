from __future__ import annotations

import subprocess
from pathlib import Path

from qa_copilot.models import Listing
from qa_copilot.policy import PolicyError
from qa_copilot.store import Workspace


def _github_repo_slug(listing: Listing) -> str | None:
    repo_url = str(listing.extra.get("repo_url") or "")
    if repo_url.startswith("https://api.github.com/repos/"):
        return repo_url.removeprefix("https://api.github.com/repos/")
    if listing.url.startswith("https://github.com/"):
        parts = listing.url.removeprefix("https://github.com/").split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return None


def prepare(ws: Workspace, listing: Listing, *, clone: bool = True) -> Path:
    job = ws.job_dir(listing.id)
    sandbox = job / "sandbox"
    evidence = job / "evidence"
    sandbox.mkdir(exist_ok=True)
    evidence.mkdir(exist_ok=True)

    brief = [
        f"# Brief `{listing.id}`",
        "",
        f"- Source: `{listing.source}`",
        f"- Title: {listing.title}",
        f"- URL: {listing.url}",
        f"- Company: {listing.company or '-'}",
        f"- Test target: {listing.test_target or '(none)'}",
        f"- Permission to test: {listing.permission_to_test}",
        f"- Client allows AI: {listing.client_allows_ai}",
        "",
        "## Description",
        "",
        listing.description or "(empty)",
        "",
        "## Guardrails",
        "",
        "- Do not apply, comment, bid, or open a PR from this tool.",
        "- Do not hit a third-party site unless `permission_to_test` is true.",
        "- Do not feed secrets into an LLM. Descriptions are redacted on ingest.",
        "",
    ]
    (job / "brief.md").write_text("\n".join(brief), encoding="utf-8")

    slug = _github_repo_slug(listing)
    if clone and slug and listing.source.startswith("github"):
        dest = sandbox / slug.replace("/", "__")
        if not dest.exists():
            clone_url = f"https://github.com/{slug}.git"
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", clone_url, str(dest)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
                raise PolicyError(f"git clone failed for {slug}: {exc}") from exc
        (job / "repo.txt").write_text(slug + "\n", encoding="utf-8")

    ws.save_json(
        listing.id,
        "stage.json",
        {"stage": "prepared", "sandbox": str(sandbox), "evidence": str(evidence)},
    )
    return job
