## What this PR does
<!-- One sentence summary. Be specific — "UI change" is not enough. -->

## Type of change
- [ ] Bug fix
- [ ] New tool (adds to agent capabilities)
- [ ] New data source / ingestion
- [ ] UI change
- [ ] Docs / context files only

---

## Pre-merge checklist

> **Every applicable checkbox must be checked before merge.** If a section doesn't apply, write "N/A" next to it. Do not leave boxes unchecked and unmarked — reviewers will send the PR back.

### Always (required for every PR)
- [ ] `conda activate powracle && streamlit run app.py` starts without errors
- [ ] Tested at least 2 canonical questions end-to-end (see CLAUDE.md for the list)
- [ ] No `.env`, `data/`, `*.duckdb`, or `*.parquet` files staged (`git status` is clean of these)
- [ ] No relative paths introduced — all use `Path(__file__).resolve().parent.parent`
- [ ] No system Python used — conda `powracle` env only

### Documentation (required for every code change)
> Every code change must update the relevant docs **in the same PR**. Do not open a separate docs PR.
- [ ] Root `CLAUDE.md` updated (tool table, UI details, env vars — whichever applies)
- [ ] `AGENTS.md` updated (same sections as CLAUDE.md — these two must stay in sync)
- [ ] Relevant subdirectory `CLAUDE.md` updated (`tools/`, `ingestion/`, `db/`, or `agent/`)
- [ ] `CONTEXT_MIN.md` updated if critical rules or module gotchas changed
- [ ] `ONBOARDING.md` updated if setup steps, key rules, or context file list changed
- [ ] `README.md` updated if user-facing features, data sources, or tech stack changed

### If you added or modified a tool (`tools/`)
- [ ] Tool function accepts a single `str` and always returns a non-empty `str`
- [ ] Tool registered in `agent/agent.py` `build_agent()` tools list
- [ ] Knowledge block added/updated in `agent/prompts.py` `SYSTEM_PROMPT`
- [ ] Tool table updated in root `CLAUDE.md` and `AGENTS.md`
- [ ] `tools/CLAUDE.md` updated

### If you added a new API or external service
- [ ] Key added to your local `.env` (never committed)
- [ ] Key name documented in `CLAUDE.md`, `AGENTS.md`, and `README.md` under API keys / `.env`
- [ ] Graceful fallback implemented when key is absent

### If you added or changed ingestion (`ingestion/`)
- [ ] `ingestion/CLAUDE.md` updated
- [ ] If new data source: new phase block added to `db/setup.py`

### If you changed the DuckDB schema or views (`db/`)
- [ ] `db/setup.py` updated
- [ ] `db/CLAUDE.md` tables and views section updated
- [ ] PR description explains how reviewer should rebuild DuckDB locally

### If you changed the agent (`agent/`)
- [ ] `agent/CLAUDE.md` updated if `build_agent()` structure or `SYSTEM_PROMPT` sections changed

### If you changed the UI (`app.py`)
- [ ] `streamlit run app.py` renders without errors or layout breakage
- [ ] Briefly describe what changed and why in the "What this PR does" section above
- [ ] `CLAUDE.md` UI details section updated with the new feature
- [ ] `AGENTS.md` UI features section updated

### Design principles (reviewer will check these)
> These protect the original architecture. If your PR violates any of them, explain why in the PR description.
- [ ] No existing modules rewritten — changes are additive
- [ ] Absolute paths preserved (`Path(__file__).resolve().parent.parent`)
- [ ] `.env` loading uses explicit path, not implicit `load_dotenv()`
- [ ] No duplicate logic introduced — shared helpers used where possible
- [ ] Tool failures return actionable messages, never raise exceptions
- [ ] LangChain version unchanged (`langchain-classic==1.0.1`)

---

## How to rebuild DuckDB locally (fill in only if schema changed)
```bash
# Only needed if this PR changes db/setup.py or ingestion scripts
PYTHONPATH=... /opt/anaconda3/envs/powracle/bin/python db/setup.py
```
