# Colorado Powracle — Contributor Onboarding

Welcome to the project. This guide covers everything you need to start contributing, including how to work effectively with AI coding assistants.

---

## 1. Get access

- **Repo:** https://github.com/Ttopiac/colorado-powracle
- **API keys:** ask the project owner for `.env` values (`OPENROUTER_API_KEY`, `SERPAPI_API_KEY`, `COTRIP_API_KEY`)
- **PostgreSQL**: required for the user accounts feature — see section 1a below

For installation and environment setup, follow the [README](README.md).

Two ways to run:
- **Streamlit UI**: `streamlit run app.py` → browser at localhost:8501
- **FastAPI API**: `uvicorn api:app --reload` → docs at localhost:8000/docs

### 1a. PostgreSQL setup (optional — for user accounts)

The app supports user accounts (pass tracking, trip planning, ROI) via PostgreSQL.

**Option A — Docker (recommended):**
```bash
# Start Postgres via Docker
docker-compose up -d

# Verify it's running
docker-compose ps
```

**Option B — Native PostgreSQL:**
```bash
# Install PostgreSQL for your OS, then create the database and user:
psql -U postgres -c "CREATE USER powracle_user WITH PASSWORD 'your_password';"
psql -U postgres -c "CREATE DATABASE powracle OWNER powracle_user;"
```

**Then for both options — add to your `.env`:**
```
DATABASE_URL=postgresql://powracle_user:your_password@localhost:5432/powracle
```

**Run migrations (idempotent — safe to run multiple times):**
```bash
conda activate powracle
PYTHONPATH=/path/to/colorado_powder_oracle \
  /opt/anaconda3/envs/powracle/bin/python db/run_migrations.py
```

**Dependencies** — all packages including PostgreSQL drivers are in `requirements.txt`. If you haven't installed yet:
```bash
conda activate powracle
pip install -r requirements.txt
```

**Verify the setup:**
```bash
psql postgresql://powracle_user:your_password@localhost:5432/powracle -c "\dt"
# Should list: users, user_passes, trips, trip_days
```

---

## 2. Branch workflow

Never commit directly to `main`. Always work on a feature branch:

```bash
git checkout -b your-name/what-youre-doing
# e.g. git checkout -b jane/add-avalanche-tool
```

When ready, open a pull request against `main`. The PR description will auto-populate with a checklist — go through it before requesting a review.

---

## 3. Project context files

The repo ships with context files that explain the architecture, rules, and gotchas. **Read these before writing any code** — they'll save you from the non-obvious mistakes.

| File | Purpose | Update when |
|------|---------|-------------|
| [CLAUDE.md](CLAUDE.md) | Primary project context for Claude Code | Any architectural or feature change |
| [AGENTS.md](AGENTS.md) | Project context for Cursor/Windsurf/Copilot (must stay in sync with CLAUDE.md) | Same as CLAUDE.md |
| [CONTEXT_MIN.md](CONTEXT_MIN.md) | Minimal rules + gotchas for quick chatbox paste | Critical rules or gotchas change |
| [README.md](README.md) | Public-facing docs, setup guide, feature list | User-facing features, data sources, or tech stack change |
| [tools/CLAUDE.md](tools/CLAUDE.md) | Tool contracts, routing logic, how to add a tool | Tools added or modified |
| [ingestion/CLAUDE.md](ingestion/CLAUDE.md) | Ingestion scripts, API quirks, data flow | Ingestion or API changes |
| [db/CLAUDE.md](db/CLAUDE.md) | DuckDB schema, views, when to rebuild | Schema or view changes |
| [agent/CLAUDE.md](agent/CLAUDE.md) | Agent architecture, SYSTEM_PROMPT, LangChain notes | Agent logic or prompt changes |
| [.github/pull_request_template.md](.github/pull_request_template.md) | PR checklist (auto-populates on PR creation) | New checklist items needed |

---

## 4. Working with AI coding assistants

### AI coding tools (Claude Code, Cursor, Windsurf, etc.)

These tools read the context files automatically when you open the repo. No extra setup needed — your AI already knows the project rules.

- **Claude Code:** reads [CLAUDE.md](CLAUDE.md) at the root and in whichever subdirectory you're working in
- **Cursor / Windsurf / others:** reads [AGENTS.md](AGENTS.md) at the root

### AI chatboxes (ChatGPT, Claude.ai, Gemini, etc.)

Your AI won't read the repo automatically. Choose how much context to paste or attach based on your task:

**Option A — Full context** (new features, unfamiliar module, or first time contributing)
1. Paste or attach [AGENTS.md](AGENTS.md) — full architecture, rules, and gotchas
2. Also paste or attach the subdirectory file for the module you're working on:

| Working on | Also paste or attach |
|------------|------------|
| Adding or editing a tool | [tools/CLAUDE.md](tools/CLAUDE.md) |
| Fetching data / API changes | [ingestion/CLAUDE.md](ingestion/CLAUDE.md) |
| Database schema or queries | [db/CLAUDE.md](db/CLAUDE.md) |
| Agent logic or system prompt | [agent/CLAUDE.md](agent/CLAUDE.md) |

3. Paste or attach the specific file(s) you want to change and describe what you need.

**Option B — Minimal context** (small edits or bug fixes where you already know the codebase)
Paste or attach just [CONTEXT_MIN.md](CONTEXT_MIN.md) + the specific file(s) you want to change.

If Option B produces wrong or inconsistent output, switch to Option A.

---

## 5. Before opening a PR

When you open a pull request, GitHub will auto-populate the description with a conditional checklist. Go through every applicable section before requesting a review.

Key things it checks:
- App starts without errors (`streamlit run app.py`)
- At least 2 canonical test questions work end-to-end
- No `.env`, `data/`, `*.duckdb`, or `*.parquet` files staged
- If you added a tool — it's registered in `agent.py`, `prompts.py`, and the docs
- If you changed the DB schema — `db/setup.py` and [db/CLAUDE.md](db/CLAUDE.md) are updated

**AI agents:** the pre-merge checklist is also in [AGENTS.md](AGENTS.md). If you ask your AI to open a PR, it should run through the checklist automatically before doing so.

---

## 6. Key rules (do not break these)

1. **No relative paths.** All scripts use `Path(__file__).resolve().parent.parent`. Never change to relative paths.
2. **SNOTEL network code is `SNTL`, not `SNOTEL`.** Station IDs use format `XXX:CO:SNTL`.
3. **Never commit secrets.** `.env` is gitignored — keep it that way.
4. **Never run `db/setup.py` mid-session.** It drops and recreates all tables.
5. **Every change is additive.** Do not rewrite existing modules — extend them.
6. **No duplicate logic.** If the same code appears in two places, extract a shared helper function.
7. **Update ALL relevant docs in the same PR.** Every code change must update the applicable docs listed in section 3 above. The PR template checklist enforces this — reviewers will send back PRs with unchecked doc boxes.
