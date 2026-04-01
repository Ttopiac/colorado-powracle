# Colorado Powracle — Minimal Context

Paste this into your AI chatbox for quick, focused tasks.
For new features or unfamiliar modules, use AGENTS.md instead.

## What this project is
LangChain ski conditions agent + Streamlit UI + FastAPI endpoint. Skier asks a question → agent calls tools → grounded answer.
Stack: SNOTEL REST API, COtrip REST API, DuckDB, LangChain `zero-shot-react-description`, Claude 3 Haiku via OpenRouter.
Two entry points: `app.py` (Streamlit UI), `api.py` (FastAPI `POST /chat`). Both use `agent/chat_service.py` for shared chat logic.

## Critical rules
1. **Absolute paths only** — always `Path(__file__).resolve().parent.parent`. Never relative paths.
2. **SNOTEL network code is `SNTL`**, not `SNOTEL`. Station IDs: `XXX:CO:SNTL`.
3. **`load_dotenv()` uses explicit path** to `<project_root>/.env`. Do not switch to implicit loading.
4. **Adding a tool requires 4 changes**: `tools/`, `agent/agent.py` tools list, `agent/prompts.py` SYSTEM_PROMPT, and docs.
5. **Never run `db/setup.py` mid-session** — drops and recreates all tables.
6. **Every change is additive** — do not rewrite existing modules, extend them.
7. **Never commit** `.env`, `data/`, `*.duckdb`, `*.parquet`.

## Module gotchas
- **tools/**: functions must accept a single `str` and always return a non-empty `str`. Never return `None`.
- **ingestion/snotel_live.py**: SNOTEL `/data` response wraps elements under a nested `"data"` key — iterate `station.get("data", [])`.
- **ingestion/cotrip_live.py**: `summarise_corridor()` returns `None` when API key is absent — the tool catches this, do not change that pattern.
- **ingestion/**: some resorts share a SNOTEL station and use `.alias` pointer files in `data/raw/snotel/` — do not delete them.
- **agent/**: uses `langchain-classic==1.0.1`. Do not upgrade without full regression testing.
- **resorts.py**: shared helpers (`pass_filter`, `haversine_miles`, `STARTING_CITIES`, `ALL_PASSES`) live here — import them, don't duplicate.
- **api.py**: lazy agent init via `_get_agent()`, TTL-based caching (no Streamlit dependency). `verbose=True` for debugging.
- **agent/deterministic_answers.py**: opt-in deterministic path for simple factual questions. Returns `None` for anything it can't handle → agent fallback.
