# Colorado Powracle — Contributor Onboarding

Welcome to the project. This guide covers everything you need to start contributing, including how to work effectively with AI coding assistants.

---

## 1. Get access

- **Repo:** https://github.com/Ttopiac/colorado-powracle
- **API keys:** ask the project owner for `.env` values (`OPENROUTER_API_KEY`, `SERPAPI_API_KEY`, `COTRIP_API_KEY`)

For installation and environment setup, follow the [README](README.md).

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

| File | Purpose |
|------|---------|
| `AGENTS.md` | Full project overview, tool contracts, critical rules, module gotchas, pre-merge checklist |
| `CLAUDE.md` | Same as above, extended for Claude Code users |
| `tools/CLAUDE.md` | How to add a tool, tool contracts, routing logic |
| `ingestion/CLAUDE.md` | Each ingestion script, API quirks, data flow |
| `db/CLAUDE.md` | DuckDB schema, views, when to rebuild |
| `agent/CLAUDE.md` | Agent architecture, SYSTEM_PROMPT structure, LangChain version notes |

---

## 4. Working with AI coding assistants

### AI coding tools (Claude Code, Cursor, Windsurf, etc.)

These tools read the context files automatically when you open the repo. No extra setup needed — your AI already knows the project rules.

- **Claude Code:** reads `CLAUDE.md` at the root and in whichever subdirectory you're working in
- **Cursor / Windsurf / others:** reads `AGENTS.md` at the root

### AI chatboxes (ChatGPT, Claude.ai, Gemini, etc.)

Your AI won't read the repo automatically. Choose how much context to paste based on your task:

**Option A — Minimal (quick focused tasks)**
Paste just `CONTEXT_MIN.md` + the specific file(s) you want to change. Good for small edits where you already know the codebase.

**Option B — Full (new features or unfamiliar modules)**
1. Paste `AGENTS.md` — full architecture, rules, and gotchas
2. Also paste the subdirectory file for the module you're working on:

| Working on | Also paste |
|------------|------------|
| Adding or editing a tool | `tools/CLAUDE.md` |
| Fetching data / API changes | `ingestion/CLAUDE.md` |
| Database schema or queries | `db/CLAUDE.md` |
| Agent logic or system prompt | `agent/CLAUDE.md` |

3. Paste the specific file(s) you want to change and describe what you need.

If Option A produces wrong or inconsistent output, switch to Option B.

---

## 5. Before opening a PR

When you open a pull request, GitHub will auto-populate the description with a conditional checklist. Go through every applicable section before requesting a review.

Key things it checks:
- App starts without errors (`streamlit run app.py`)
- At least 2 canonical test questions work end-to-end
- No `.env`, `data/`, `*.duckdb`, or `*.parquet` files staged
- If you added a tool — it's registered in `agent.py`, `prompts.py`, and the docs
- If you changed the DB schema — `db/setup.py` and `db/CLAUDE.md` are updated

**AI agents:** the pre-merge checklist is also in `AGENTS.md`. If you ask your AI to open a PR, it should run through the checklist automatically before doing so.

---

## 6. Key rules (do not break these)

1. **No relative paths.** All scripts use `Path(__file__).resolve().parent.parent`. Never change to relative paths.
2. **SNOTEL network code is `SNTL`, not `SNOTEL`.** Station IDs use format `XXX:CO:SNTL`.
3. **Never commit secrets.** `.env` is gitignored — keep it that way.
4. **Never run `db/setup.py` mid-session.** It drops and recreates all tables.
5. **Every change is additive.** Do not rewrite existing modules — extend them.
6. **Update the docs alongside the code.** If you change architecture, update `CLAUDE.md`, `AGENTS.md`, and the relevant subdirectory `CLAUDE.md` in the same PR.
