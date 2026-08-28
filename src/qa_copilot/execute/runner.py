from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from qa_copilot.httputil import USER_AGENT
from qa_copilot.models import Finding, Listing, RunReport, utc_now
from qa_copilot.policy import PolicyError
from qa_copilot.store import Workspace

MAX_BYTES = 1_000_000


class _Scan(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_bits: list[str] = []
        self.in_title = False
        self.imgs_missing_alt = 0
        self.inputs_missing_labelish = 0
        self.html_lang = ""
        self.h1 = 0
        self.buttons_empty = 0
        self._btn = False
        self._btn_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.html_lang = ad.get("lang", "")
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.h1 += 1
        if tag == "img" and not ad.get("alt"):
            self.imgs_missing_alt += 1
        if tag == "input" and ad.get("type") not in {"hidden", "submit", "button"}:
            if not ad.get("aria-label") and not ad.get("id") and not ad.get("name"):
                self.inputs_missing_labelish += 1
        if tag == "button":
            self._btn = True
            self._btn_text = ad.get("aria-label", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "button":
            if not self._btn_text.strip():
                self.buttons_empty += 1
            self._btn = False
            self._btn_text = ""

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_bits.append(data)
        if self._btn:
            self._btn_text += data


def _robots_allows(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(robots_url)
            if resp.status_code == 404:
                return True, "no robots.txt (404) — proceeding cautiously"
            if resp.status_code >= 400:
                return False, f"robots.txt HTTP {resp.status_code}; refusing to guess"
            rp.parse(resp.text.splitlines())
    except httpx.HTTPError as exc:
        return False, f"could not fetch robots.txt: {exc}"
    allowed = rp.can_fetch(USER_AGENT, url) and rp.can_fetch("*", url)
    return allowed, "robots.txt allow" if allowed else "robots.txt disallow"


def _scan_html(text: str) -> _Scan:
    parser = _Scan()
    parser.feed(text)
    return parser


def _http_check(url: str, evidence: Path) -> list[Finding]:
    findings: list[Finding] = []
    allowed, reason = _robots_allows(url)
    (evidence / "robots-decision.txt").write_text(reason + "\n", encoding="utf-8")
    if not allowed:
        findings.append(
            Finding("info", "Skipped live fetch", reason, evidence="robots-decision.txt", verified=True)
        )
        return findings
    with httpx.Client(timeout=20.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(url)
    body = resp.text[:MAX_BYTES]
    (evidence / "response-headers.txt").write_text(
        f"status {resp.status_code}\nfinal {resp.url}\ncontent-type {resp.headers.get('content-type')}\n",
        encoding="utf-8",
    )
    (evidence / "body-snippet.html").write_text(body[:20000], encoding="utf-8")
    if resp.status_code >= 400:
        findings.append(
            Finding("major", f"HTTP {resp.status_code}", str(resp.url), "response-headers.txt", verified=True)
        )
    parser = _scan_html(body)
    title = html.unescape("".join(parser.title_bits)).strip()
    if not title:
        findings.append(Finding("minor", "Missing document title", url, "body-snippet.html"))
    if not parser.html_lang:
        findings.append(Finding("minor", "html[lang] missing", "WCAG 3.1.1 Language of Page", "body-snippet.html"))
    if parser.h1 == 0:
        findings.append(Finding("minor", "No h1", "Page has no top-level heading", "body-snippet.html"))
    if parser.imgs_missing_alt:
        findings.append(
            Finding("major", f"{parser.imgs_missing_alt} image(s) missing alt", url, "body-snippet.html")
        )
    if parser.buttons_empty:
        findings.append(
            Finding("major", f"{parser.buttons_empty} button(s) with no accessible name", url, "body-snippet.html")
        )
    if not findings:
        findings.append(
            Finding("info", "Smoke fetch succeeded", f"{resp.status_code} {title or resp.url}", "response-headers.txt", True)
        )
    return findings


def _local_html(path: Path, evidence: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8", errors="replace")[:MAX_BYTES]
    (evidence / "local-source.txt").write_text(str(path), encoding="utf-8")
    parser = _scan_html(text)
    findings: list[Finding] = []
    if not parser.html_lang:
        findings.append(Finding("minor", "html[lang] missing", str(path), "local-source.txt"))
    if parser.imgs_missing_alt:
        findings.append(Finding("major", f"{parser.imgs_missing_alt} image(s) missing alt", str(path)))
    if parser.buttons_empty:
        findings.append(Finding("major", f"{parser.buttons_empty} unnamed button(s)", str(path)))
    if parser.h1 == 0:
        findings.append(Finding("minor", "No h1", str(path)))
    if not findings:
        findings.append(Finding("info", "Local HTML smoke passed", str(path), verified=True))
    return findings


def execute(ws: Workspace, listing: Listing) -> RunReport:
    job = ws.job_dir(listing.id)
    evidence = job / "evidence"
    evidence.mkdir(exist_ok=True)
    findings: list[Finding] = []
    notes: list[str] = [
        "Findings are machine-assisted. A human must verify before any client-facing report.",
        "No exploits, payloads, credential stuffing, or destructive actions are performed.",
    ]

    target = listing.test_target
    if target.startswith("file:"):
        path = Path(target.removeprefix("file:")).expanduser()
        if not path.is_file():
            raise PolicyError(f"local fixture not found: {path}")
        findings.extend(_local_html(path, evidence))
    elif target and listing.permission_to_test:
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"}:
            raise PolicyError(f"refusing non-http test_target: {target}")
        findings.extend(_http_check(target, evidence))
    elif target and not listing.permission_to_test:
        notes.append("test_target set but permission_to_test is false — did not fetch it.")
        findings.append(
            Finding("info", "Plan-only", "No live test without explicit permission_to_test: true", verified=True)
        )
    elif listing.source.startswith("github"):
        sandbox = job / "sandbox"
        repos = list(sandbox.glob("*")) if sandbox.exists() else []
        if repos:
            notes.append(f"Repo cloned at {repos[0]}. Look for test runners; this minimal build does not invent exploits.")
            findings.append(
                Finding(
                    "info",
                    "Repository prepared",
                    "Inspect tests in sandbox. Human decides whether to run them.",
                    verified=True,
                )
            )
        else:
            findings.append(Finding("info", "No clone", "Run prepare first if you want a local checkout."))
    else:
        findings.append(
            Finding(
                "info",
                "No executable target",
                "Job-board cards are not permission to test the employer's production site.",
                verified=True,
            )
        )
        notes.append("Generate a test plan in the report. Do not probe the company website from a job ad alone.")

    blockers = sum(1 for f in findings if f.severity == "blocker")
    majors = sum(1 for f in findings if f.severity == "major")
    summary = f"{len(findings)} finding(s): {blockers} blocker, {majors} major. Unverified until human review."
    report = RunReport(
        listing_id=listing.id,
        generated_at=utc_now(),
        findings=findings,
        summary=summary,
        evidence_dir=str(evidence),
        unverified=True,
        notes=notes,
    )
    ws.save_json(listing.id, "findings.json", report.to_dict())
    ws.save_json(listing.id, "stage.json", {"stage": "executed"})
    return report
