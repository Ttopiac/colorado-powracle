## What this PR does
<!-- One sentence summary -->

## Type of change
- [ ] Bug fix
- [ ] New tool (adds to agent capabilities)
- [ ] New data source / ingestion
- [ ] UI change
- [ ] Docs / context files only

---

## Pre-merge checklist

### Always
- [ ] `conda activate powracle && streamlit run app.py` starts without errors
- [ ] Tested at least 2 canonical questions end-to-end (see AGENTS.md for the list)
- [ ] No `.env`, `data/`, `*.duckdb`, or `*.parquet` files staged (`git status` is clean of these)
- [ ] No relative paths introduced — all use `Path(__file__).resolve().parent.parent`
- [ ] No system Python used — conda `powracle` env only

### If you added or modified a tool (`tools/`)
- [ ] Tool function accepts a single `str` and always returns a non-empty `str`
- [ ] Tool registered in `agent/agent.py` `build_agent()` tools list
- [ ] Knowledge block added/updated in `agent/prompts.py` `SYSTEM_PROMPT`
- [ ] Tool table updated in root `CLAUDE.md` and `AGENTS.md`
- [ ] `tools/CLAUDE.md` updated

### If you added a new API or external service
- [ ] Key added to your local `.env` (never committed)
- [ ] Key name documented in `CLAUDE.md` and `AGENTS.md` under `.env file`
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

---

## How to rebuild DuckDB locally (fill in only if schema changed)
```bash
# Only needed if this PR changes db/setup.py or ingestion scripts
PYTHONPATH=... /opt/anaconda3/envs/powracle/bin/python db/setup.py
```
