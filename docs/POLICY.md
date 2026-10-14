# Source policy (researched 2026-08-28)

This file is the human-readable twin of `src/qa_copilot/policy.py`.
The Python module is the source of truth at runtime. If they drift, fix the code first.

**Product rule:** this is not a job-accepting bot. It discovers work, scores it, prepares a sandbox, helps run QA, and writes a report. A human must approve before any application text is even *exported*. The tool never posts, bids, comments, or messages a marketplace.

## Modes

| Mode | Meaning |
| --- | --- |
| `official_api` | HTTP GET only to documented public/official endpoints on an allowlisted host. |
| `paste_only` | User copies a listing they already opened in a browser. No HTTP to that marketplace. |
| `disabled` | Not used. Config cannot turn these on. |

Write modes: `never` (job boards) or `approval_required` (GitHub comments/PRs, marketplace applications). Even then, the tool only writes a local `packet/APPLY.md`.

Only `github_issues` / `github_bounties` and the paste-only marketplaces can be written to at all, and only after a signed approval packet. Everything the tool sends verbatim is written by a human.

## Matrix

| Source | Access | Write | AI / automation | Why this tool treats it that way |
| --- | --- | --- | --- | --- |
| GitHub Issues | official API | approval | Machine accounts allowed if a human owns them. API use is not HTML scraping. Spam / inauthentic bulk activity is banned. | Search + clone are in-scope. Comments/PRs are packet-only. |
| GitHub bounty labels | official API | approval | Same. | Discover via Search API (`bounty`, `💎 Bounty`). Payout amounts are parsed for triage. |
| Remotive | official API | never | Public jobs API for sharing listings. Attribution required. Do not republish onto other boards. ≤2 req/min. | Read-only cards. Apply in a browser. |
| Remote OK | official API | never | Public `/api`. Link back. ~24h delay. Do not use their logo. | Read-only. |
| Jobicy | official API | never | Documented public remote-jobs API. | Read-only. |
| Himalayas | official API | never | Public jobs JSON. | Read-only. |
| Working Nomads | official API | never | Public `/api/exposed_jobs/`. | Read-only. |
| Arbeitnow | official API | never | Public job-board feed published by Arbeitnow for other boards to consume. | Read-only. CNC/embedded "test" roles are filtered out by qualify. |
| 4 Day Week | official API | never | Public jobs JSON backing the board. | Read-only. |
| Careerjet | official API | never | Public aggregator search API. Requires a `Referer` header identifying the caller and an affiliate id; the endpoint is http-only and rate-limits hard (401/429 under bursts). | Read-only. `CAREERJET_LOCALES` covers `ja_JP` and `en_GB` in one run. |
| Adzuna | official API | never | Official search API, country-parameterised. Requires the user's own free `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`. | Read-only. One source covers English and Japanese markets. |
| Hacker News "Who is hiring" | official API | never | Public Algolia HN Search API. Reads the monthly thread and its comments; no HTML scraping of news.ycombinator.com. | Read-only. Comments often state salary; salaries are not treated as bounties. Reply by email. |
| Paste inbox | paste | approval | N/A (local files). | Default path for JP marketplaces and Upwork copies. |
| CrowdWorks | paste | approval | Official AI policy (2024, still published 2026): AI use is **not banned**; it is between client and worker. Hide nothing. Quality still required. Job-offer guideline forbids scraping / automating services that do not allow it, and forbids asking workers to do that. ToS §23 forbids unauthorized access, DoS, and using the site for non-matching commercial activity. | No worker job API. Paste the page you opened. |
| Lancers | paste | approval | Clients can mark generative-AI allowed/restricted (contest UI, 2024). Auto-proposal was **retired** (2026-03) in favor of confirm-then-propose. ToS §31-15 forbids commercial reuse of site content; §31-16 forbids high-load / unauthorized access / reverse engineering. | Paste only. Honor the job's AI flag. |
| Coconala | paste | approval | AI *illustrations* are restricted. AI articles/photos have conditions. Automated tools against Coconala features are prohibited. ToS §13(22) forbids auto-responders on purchased content. | Do not HTTP-automate Coconala. |
| Upwork | paste | approval | Official help: bots = anything faster than a human. Unauthorized automation (including many "productivity" extensions) can ban you. Official API requires an approved key. Auto-submit proposals is banned. AI drafts with human edit + manual send are widely described as allowed. | **Changed (2026-10): paste-only, no longer disabled.** The ban is on automation, not on a human copying a listing into a local tool. This tool still never speaks HTTP to Upwork, and `upwork` is never discoverable. Auto-bid remains impossible. |
| Freelancer.com | disabled | never | Official API exists (API T&Cs 2017). Circumventing rate limits / competing with the site is banned. Bidding via API is a later, approval-gated feature — not in this minimal build. | Out of scope. |
| UserTesting | disabled | never | Contributor Code of Conduct: do not use AI-generated responses on the platform. | Agent-incompatible. |
| uTest | disabled | never | No emulators/simulators/remote machines/jailbreaks unless staff say so. Real-device, often identity-bound. | Agent-incompatible. |
| HackerOne | disabled | never | AI-assisted research is allowed. Fully autonomous hackbots are not. Human must validate a real PoC. Slop / hallucinated reports are a CoC violation. | Not a QA-report mill. Do not auto-submit. |
| Bugcrowd | disabled | never | Unvalidated AI volume ("sloptimism") is being enforced (2026-03): farming bans, identity checks after invalid streaks. | Not implemented. |

## What an agent can reasonably help with

Fit (this repo):

- Reproduce a public GitHub issue in a shallow clone
- Draft a test plan / test cases from a spec
- Smoke + naive a11y scan of a URL the client **gave permission** to test
- Structure a bug report (steps, expected/actual, evidence)
- Accessibility / empty-button / missing-alt checks
- API smoke against a documented staging host with permission

Not fit:

- Auto-bid / auto-apply / auto-DM
- UserTesting / uTest / webcam think-aloud
- Review farming, stealth marketing, account mills
- Scraping CrowdWorks / Lancers / Coconala / Upwork
- Unscoped pentests or exploit PoCs (HackerOne/Bugcrowd need a human-validated PoC *and* program scope)
- Testing a company's production site just because they posted a job ad

## Disclosure

If the client is silent, ask. If the client forbids AI, the qualifier rejects the listing. Packet text includes a one-line disclosure template.

Do not send client secrets, NDA text, or credentials to a third-party model. Ingest redacts common token patterns; still, prefer staging fixtures.

## Primary documents

- CrowdWorks AI policy: https://blog.crowdworks.jp/archives/5811/
- CrowdWorks job-offer guideline: https://crowdworks.jp/pages/guidelines/job_offer
- CrowdWorks ToS: https://crowdworks.jp/pages/agreement
- Lancers ToS: https://www.lancers.jp/help/terms
- Lancers auto-proposal retirement: https://info.lancers.jp/34546
- Coconala AI stance: https://help.coconala.com/hc/ja/articles/48479864968729
- Coconala ToS: https://coconala.com/pages/terms_user
- Upwork automation help: https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly
- GitHub ToS (accounts + API): https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
- HackerOne Code of Conduct: https://www.hackerone.com/policies/code-of-conduct
- Bugcrowd AI-slop policy: https://www.bugcrowd.com/blog/bugcrowd-policy-changes-to-address-ai-slop-submissions/
- UserTesting contributor CoC: https://participant-support.usertesting.com/hc/en-us/articles/37395412977427-Contributor-Code-of-Conduct
- uTest rules: https://www.utest.com/rules-of-engagement
- Remotive API: https://github.com/remotive-com/remote-jobs-api
- Freelancer API T&Cs: https://www.freelancer.com/about/apiterms
- Arbeitnow job board API: https://www.arbeitnow.com/blog/job-board-api
- Careerjet partners / API: https://www.careerjet.com/partners/api/
- Adzuna developer API: https://developer.adzuna.com/
- Algolia HN Search API: https://hn.algolia.com/api

## Change log

- 2026-10: `upwork` moved from `disabled` to `paste_only`. Its terms ban automation, not a human
  copying a listing into a local editor, so pasting is allowed while HTTP stays blocked and the source
  stays undiscoverable. `usertesting` / `utest` remain disabled because the *deliverable* would be
  non-compliant, not just the discovery.
- 2026-10: added `arbeitnow`, `fourdayweek`, `careerjet`, `adzuna`, `hn_hiring` as official-API
  discovery sources, and payout extraction for triage.

Re-read these before changing `policy.py`. Terms move.
