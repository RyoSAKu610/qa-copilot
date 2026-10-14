---
name: qa-copilot
description: >
  Human-gated QA agent workflow: discover jobs from official APIs, paste
  CrowdWorks/Lancers listings, qualify, prepare a sandbox, run permitted
  checks, write a report, and stop for human approval. Never auto-apply.
  Use when the user mentions 案件, QA agent, crowdworks, lancers, freelance
  QA, or runs /qa-copilot.
---

# qa-copilot

This skill drives the `qa-copilot` CLI in the current workspace (or `~/qa-copilot`).

## Hard rules

1. Do not scrape CrowdWorks, Lancers, Coconala, or Upwork.
2. Do not bid, apply, comment, or send messages from a tool.
3. Do not test a company's production site just because they posted a job.
4. Do not submit bug-bounty reports without a human-verified PoC.
5. Do not take UserTesting or uTest tasks.
6. If `client_allows_ai` is `no` or the brief bans AI, stop.

Read `docs/POLICY.md` in the repo before expanding a source.

## Commands

```bash
qa-copilot policy
qa-copilot discover --source github_bounties,careerjet,arbeitnow
qa-copilot triage            # rank by payout then QA fit; work top-down
qa-copilot inbox add <pasted.md>
qa-copilot list
qa-copilot prepare <id>
qa-copilot execute <id>
qa-copilot report <id>
qa-copilot approve <id> --operator <human> --i-understand
qa-copilot packet <id>
```

After `packet`, tell the human to submit in the official UI. Do not offer to "just send it".

## Sources that pay

`github_bounties` is the only channel where an agent does most of the work and a human
does one click (open the PR). `careerjet` / `adzuna` cover Japanese and English markets at
once; `hn_hiring` and `arbeitnow` are English/remote. Everything else is discovery-only.

`triage` sorts by payout amount first. Bounties are parsed from text; salaries and hourly
rates are deliberately ignored so a $250k job posting does not outrank a $500 bounty.

## Paste format

```yaml
---
source: crowdworks   # or lancers | coconala | paste
title: ...
client_allows_ai: unknown   # yes | no | unknown
ai_disclosed: false
test_target: file:fixtures/site/broken.html
permission_to_test: true
---
body
```

## When helping as Grok

- Prefer GitHub issues labelled good-first-issue / bounty that are actually about tests, docs, or reproducible bugs.
- For JP cloudso, ask the user to paste the listing; do not fetch the marketplace.
- Redact tokens before any model call.
- Keep findings marked UNVERIFIED until the user says they reproduced them.
