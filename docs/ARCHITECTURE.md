# Architecture

```
discover (official API | paste)
    → qualify (rules; reject ToS-hostile / non-QA / no-AI)
        → prepare (brief.md, optional git clone)
            → execute (local fixture or permissioned URL; robots.txt honored)
                → report.md  (UNVERIFIED)
                    → human approve (checklist + operator name)
                        → packet/APPLY.md
                            → human submits in a browser
```

There is no `apply` command that talks to a marketplace.

Policy is enforced in code:

- `assert_http_allowed` checks source mode **and** hostname allowlist
- user config can only disable sources, never promote them
- `packet` refuses to run without `approval.json`

Execute will not fetch an employer's website from a job-board card. A paste must set both `test_target` and `permission_to_test: true` (or `file:` for a local fixture).
