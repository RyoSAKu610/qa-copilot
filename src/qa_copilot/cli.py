from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qa_copilot import __version__
from qa_copilot.approve.gate import CHECKLIST, approve, build_packet
from qa_copilot.discover.paste import parse_paste
from qa_copilot.discover.registry import run_discover
from qa_copilot.execute.runner import execute
from qa_copilot.models import Listing
from qa_copilot.policy import SOURCES, PolicyError
from qa_copilot.prepare.sandbox import prepare
from qa_copilot.qualify.rules import qualify
from qa_copilot.report.renderer import render_report
from qa_copilot.store import Workspace


def _ws(args: argparse.Namespace) -> Workspace:
    root = Path(args.workspace) if getattr(args, "workspace", None) else None
    return Workspace(root)


def cmd_policy(_args: argparse.Namespace) -> int:
    print(f"{'id':<18} {'access':<16} {'write':<20} name")
    print("-" * 78)
    for sid, p in SOURCES.items():
        print(f"{sid:<18} {p.access.value:<16} {p.write.value:<20} {p.display_name}")
    print("\nUser config cannot enable a disabled source or turn paste-only into HTTP.")
    print("See docs/POLICY.md for the research notes (researched 2026-08-28).")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    ws = _ws(args)
    sources = args.source.split(",") if args.source else None
    listings, errors = run_discover(sources, limit=args.limit)
    scored: list[tuple[Listing, object]] = []
    for listing in listings:
        q = qualify(listing)
        ws.save_listing(listing)
        ws.save_qualification(q)
        scored.append((listing, q))
    scored.sort(key=lambda pair: (pair[1].payout_usd or 0, pair[1].score), reverse=True)  # type: ignore[union-attr]
    for listing, q in scored:
        pay = f"${q.payout_usd:>8,.0f}" if q.payout_usd else f"{'-':>9}"  # type: ignore[union-attr]
        print(f"{q.verdict:12} {q.score:3} {pay}  {listing.id}  [{listing.source}] {listing.title[:60]}")  # type: ignore[union-attr]
    for err in errors:
        print(f"! {err}", file=sys.stderr)
    print(f"\n{len(listings)} listing(s) saved under {ws.listings_dir}")
    return 0


def cmd_triage(args: argparse.Namespace) -> int:
    ws = _ws(args)
    wanted = None if args.all else {"candidate"}
    rows: list[tuple[Listing, object]] = []
    for listing in ws.iter_listings():
        q = ws.load_qualification(listing.id) or qualify(listing)
        if wanted and getattr(q, "verdict") not in wanted:
            continue
        rows.append((listing, q))
    if not rows:
        print("nothing to triage. run discover or inbox add first (try --all).")
        return 0
    # Expected value = money first, then QA fit. This is the whole point of triage.
    rows.sort(key=lambda pair: (getattr(pair[1], "payout_usd") or 0, getattr(pair[1], "score")), reverse=True)
    print(f"{'payout':>10} {'score':>5}  {'id':<12} {'source':<14} title")
    print("-" * 100)
    for listing, q in rows[: args.limit]:
        payout = getattr(q, "payout_usd")
        pay = f"${payout:,.0f}" if payout else "-"
        print(f"{pay:>10} {getattr(q, 'score'):>5}  {listing.id:<12} {listing.source:<14} {listing.title[:52]}")
    print(f"\n{len(rows)} in scope. Work top-down: prepare → execute → report → approve → packet.")
    return 0



def cmd_inbox_add(args: argparse.Namespace) -> int:
    ws = _ws(args)
    path = Path(args.file)
    listing = parse_paste(path)
    dest = ws.inbox_dir / path.name
    if path.resolve() != dest.resolve():
        dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    q = qualify(listing)
    ws.save_listing(listing)
    ws.save_qualification(q)
    print(f"ingested {listing.id}  verdict={q.verdict} score={q.score}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    ws = _ws(args)
    rows = ws.iter_listings()
    if not rows:
        print("no listings. run discover or inbox add.")
        return 0
    for listing in rows:
        q = ws.load_qualification(listing.id)
        verdict = q.verdict if q else "-"
        score = q.score if q else "-"
        print(f"{listing.id}  {verdict:12} {score:>3}  [{listing.source}] {listing.title[:70]}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    ws = _ws(args)
    listing = ws.load_listing(args.id)
    q = ws.load_qualification(args.id)
    print(json.dumps({"listing": listing.to_dict(), "qualification": q.to_dict() if q else None}, ensure_ascii=False, indent=2))
    return 0


def cmd_qualify(args: argparse.Namespace) -> int:
    ws = _ws(args)
    listing = ws.load_listing(args.id)
    q = qualify(listing)
    ws.save_qualification(q)
    print(f"{listing.id}  {q.verdict}  {q.score}")
    for r in q.reasons:
        print(f"  - {r}")
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    ws = _ws(args)
    listing = ws.load_listing(args.id)
    q = ws.load_qualification(args.id) or qualify(listing)
    if q.verdict == "reject" and not args.force:
        raise PolicyError("listing was rejected; pass --force if you still want a sandbox")
    job = prepare(ws, listing, clone=not args.no_clone)
    print(f"prepared {job}")
    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    ws = _ws(args)
    listing = ws.load_listing(args.id)
    run = execute(ws, listing)
    print(run.summary)
    for f in run.findings:
        print(f"  [{f.severity}] {f.title}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    ws = _ws(args)
    listing = ws.load_listing(args.id)
    q = ws.load_qualification(args.id)
    raw = ws.load_json(args.id, "findings.json")
    run = None
    if raw:
        from qa_copilot.models import Finding, RunReport

        run = RunReport(
            listing_id=raw["listing_id"],
            generated_at=raw["generated_at"],
            summary=raw["summary"],
            evidence_dir=raw["evidence_dir"],
            unverified=raw.get("unverified", True),
            notes=list(raw.get("notes") or []),
            findings=[Finding(**f) for f in raw.get("findings") or []],
        )
    text = render_report(ws, listing, q, run)
    print(text)
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    ws = _ws(args)
    listing = ws.load_listing(args.id)
    checks = {k: True for k in CHECKLIST} if args.i_understand else {}
    approve(ws, listing, args.operator, checks)
    print(f"approved {listing.id} by {args.operator}")
    return 0


def cmd_packet(args: argparse.Namespace) -> int:
    ws = _ws(args)
    listing = ws.load_listing(args.id)
    path = build_packet(ws, listing)
    print(f"packet written to {path}")
    print("Submit it yourself. This tool will not send it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="qa-copilot",
        description="Human-gated QA agent. Discovers and assists. Never auto-applies.",
    )
    p.add_argument("--workspace", default=None, help="workspace dir (default: ./.qa-copilot)")
    p.add_argument("--version", action="version", version=f"qa-copilot {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("policy", help="print the hard-coded source matrix").set_defaults(func=cmd_policy)

    d = sub.add_parser("discover", help="fetch official-API sources only")
    d.add_argument("--source", default=None, help="comma-separated source ids")
    d.add_argument("--limit", type=int, default=15)
    d.set_defaults(func=cmd_discover)

    inbox = sub.add_parser("inbox", help="manual paste inbox")
    inbox_sub = inbox.add_subparsers(dest="inbox_cmd", required=True)
    add = inbox_sub.add_parser("add", help="ingest a pasted listing markdown/yaml file")
    add.add_argument("file")
    add.set_defaults(func=cmd_inbox_add)

    sub.add_parser("list", help="list saved listings").set_defaults(func=cmd_list)

    tri = sub.add_parser("triage", help="rank candidates by payout x QA fit")
    tri.add_argument("--all", action="store_true", help="include needs_human as well as candidates")
    tri.add_argument("--limit", type=int, default=25)
    tri.set_defaults(func=cmd_triage)

    s = sub.add_parser("show", help="show one listing")
    s.add_argument("id")
    s.set_defaults(func=cmd_show)

    q = sub.add_parser("qualify", help="re-score a listing")
    q.add_argument("id")
    q.set_defaults(func=cmd_qualify)

    pr = sub.add_parser("prepare", help="write brief + optional git clone")
    pr.add_argument("id")
    pr.add_argument("--force", action="store_true")
    pr.add_argument("--no-clone", action="store_true")
    pr.set_defaults(func=cmd_prepare)

    ex = sub.add_parser("execute", help="run local/permissioned checks")
    ex.add_argument("id")
    ex.set_defaults(func=cmd_execute)

    rp = sub.add_parser("report", help="write report.md")
    rp.add_argument("id")
    rp.set_defaults(func=cmd_report)

    ap = sub.add_parser("approve", help="human sign-off")
    ap.add_argument("id")
    ap.add_argument("--operator", required=True)
    ap.add_argument(
        "--i-understand",
        action="store_true",
        help="assert you read the report, verified findings, accept ToS, will submit manually, will disclose AI",
    )
    ap.set_defaults(func=cmd_approve)

    pk = sub.add_parser("packet", help="write a manual APPLY.md — does not send")
    pk.add_argument("id")
    pk.set_defaults(func=cmd_packet)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PolicyError as exc:
        print(f"policy: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
