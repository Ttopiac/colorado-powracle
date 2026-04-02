---
name: review-pr
description: Review ALL open pull requests against the project PR template, fix their bodies, post detailed comments, and update the PR template itself if new checks are discovered.
argument-hint: "[optional: pr-number to review a single PR]"
allowed-tools: Bash, Read, Glob, Grep, Edit, Write
---

# PR Template Reviewer

Review open pull requests, enforce template compliance, post detailed audit comments, and keep the PR template up to date with any new rules discovered during review.

## Steps

### 1. Load the template
Read `.github/pull_request_template.md` in full before doing anything else.

### 2. Get the full PR list
- If `$ARGUMENTS` is a specific PR number, review only that PR.
- Otherwise: `gh pr list --state open --json number,title,headRefName`
- **Review every PR in the list — do not skip any.**
- Keep a running log of every new rule or check category discovered across all PRs.

### 3. For each PR — gather facts
```bash
gh pr view <NUMBER> --json number,title,body,headRefName
gh pr diff <NUMBER> --name-only
```

Determine which sections apply based on changed files:
| Changed path | Applicable section |
|---|---|
| `tools/` | If you added or modified a tool |
| `ingestion/` | If you added or changed ingestion |
| `db/` | If you changed the DuckDB schema or views |
| `agent/` | If you changed the agent |
| `app.py` | If you changed the UI |
| New external service / API key | If you added a new API or external service |
| New infrastructure (Docker, Postgres, etc.) | New infrastructure checklist |

Also scan for files that must never be committed:
- `.env`, `data/`, `*.duckdb`, `*.parquet`
- `.claude/settings.local.json` (machine-local Claude Code config)
- `eval/results/`, `*.json` output dumps, any timestamped artifact files
- `requirements_*.txt` that shadow the main env without being documented

### 4. For each PR — draft the updated body
- Keep the author's original description in "What this PR does" (improve clarity if vague).
- Check the correct "Type of change" box(es) inferred from changed files.
- For every checklist section:
  - Mark "N/A" if the section clearly does not apply.
  - Leave unchecked (with an inline note) for items the author must verify at runtime.
  - Check only items that can be verified from the diff alone.
- Flag any committed artifacts or sensitive files at the top of the body with a `> **Note for reviewer:**` block.

### 5. For each PR — update the body and post a comment
```bash
gh pr edit <NUMBER> --body "..."
gh pr comment <NUMBER> --body "..."
```

The comment must include:
- A numbered list of every issue found
- For each issue: what it was, why it matters, and what was changed to fix it
- A final checklist of items the author must still complete before merge

### 6. After all PRs — update the PR template if needed
Review your running log of new checks discovered. For any check that:
- Was missing from the template and needed to be applied to one or more PRs, OR
- Represents a recurring risk not currently covered

→ Add it to `.github/pull_request_template.md` in the most relevant section.

Then post a summary comment on the most recent PR (or as a standalone issue comment) listing every rule added to the template and why.

**Current known rules to ensure are in the template:**
- No `.env`, `data/`, `*.duckdb`, `*.parquet` staged (already present)
- No `.claude/settings.local.json` committed
- No runtime artifact files committed (`eval/results/`, timestamped JSONs, output dumps)
- New infrastructure (Docker, Postgres, etc.) must be documented in `ONBOARDING.md`
- New external services must implement graceful fallback when unavailable
- `requirements_*.txt` additions must be reflected in `CLAUDE.md` / `ONBOARDING.md`

## Rules: what constitutes a template violation
- Any unchecked checkbox with no "N/A" annotation → violation
- "What this PR does" is a placeholder or too vague (< 1 specific sentence) → violation
- A section-specific checklist is entirely absent when it applies → violation
- A file that should never be committed is staged → violation, flag prominently
- A new infrastructure dependency with no doc update → violation
