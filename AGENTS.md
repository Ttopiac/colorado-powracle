# Colorado Powracle — AI Agent Context

> This file is the shared context for AI coding agents (Cursor, Windsurf, GitHub Copilot, etc.).
> Claude Code users: see CLAUDE.md — it has additional Claude-specific detail.

GitHub: https://github.com/Ttopiac/colorado-powracle (private, MIT license)

## What this project is
A LangChain-powered ski conditions agent with a Streamlit UI.
A skier asks a natural-language question → the agent calls real tools → returns a grounded answer.

Built as a Big Data Architecture project using:
- **Live snow data**: USDA NRCS SNOTEL REST API (no key required)
- **Live traffic data**: COtrip REST API (requires `COTRIP_API_KEY`)
- **Historical snow data**: 10 years of daily SNOTEL CSVs → Apache Parquet → DuckDB (40,780 rows)
- **Historical traffic data**: 10yr CDOT hourly volumes → DuckDB `traffic_patterns` view
- **Agent**: LangChain `zero-shot-react-description` via `langchain-classic`
- **LLM**: `anthropic/claude-3-haiku` via OpenRouter
- **UI**: Streamlit + Plotly Scattermapbox (ESRI World Topo tiles), Mountain Stone theme

## Project layout
```
colorado_powder_oracle/
├── app.py              # Streamlit UI (509 lines) — left panel conditions, right panel chat
├── resorts.py          # RESORT_STATIONS dict: 19 resorts, station IDs, corridors, pass info
├── agent/
│   ├── agent.py        # build_agent() — assembles LLM + 5 tools
│   └── prompts.py      # SYSTEM_PROMPT — resort knowledge, traffic patterns, decision logic
├── tools/
│   ├── snowpack_tools.py   # get_current_snowpack, get_snowpack_history
│   ├── search_tools.py     # web_search (SerpAPI)
│   └── traffic_tools.py    # get_live_traffic, get_best_departure_time
├── ingestion/
│   ├── snotel_live.py      # fetch_current_snowpack() — SNOTEL REST API
│   ├── snotel_historical.py # one-time bulk CSV download (2015–today)
│   ├── cotrip_live.py      # fetch_incidents(), summarise_corridor() — COtrip API
│   └── cdot_historical.py  # synthetic 10yr hourly traffic data generator
├── db/
│   └── setup.py        # DuckDB init: loads parquets, creates tables + views
├── data/               # gitignored — regenerate locally
│   ├── raw/snotel/     # CSVs + .alias pointer files for shared stations
│   └── raw/traffic/    # traffic_history.csv
└── .streamlit/
    └── config.toml     # Mountain Stone dark theme
```

## Environment
- **Conda env**: `powracle`
- **Python**: `/opt/anaconda3/envs/powracle/bin/python`
- **Run app**: `conda activate powracle && streamlit run app.py`

## .env file (gitignored, at project root)
```
OPENROUTER_API_KEY=...
SERPAPI_API_KEY=...
COTRIP_API_KEY=...
```

## The 5 agent tools
| Tool | Source | Returns |
|------|--------|---------|
| `get_current_snowpack` | SNOTEL REST API (live) | Base depth, SWE, new snow 24/48/72h |
| `get_snowpack_history` | DuckDB `snowpack` table | Monthly averages, season comparisons, consistency |
| `web_search` | SerpAPI | Lift status, road conditions, forecasts |
| `get_live_traffic` | COtrip REST API (live) | Incidents, chain laws, corridor conditions |
| `get_best_departure_time` | DuckDB `traffic_patterns` view | Best/worst departure windows by corridor + day |

## Critical rules — do not break these

1. **Absolute paths only.** All scripts resolve paths via `Path(__file__).resolve().parent.parent`. Never change to relative paths.
2. **SNOTEL network code is `SNTL`, not `SNOTEL`.** Station IDs in `resorts.py` use format `XXX:CO:SNTL`.
3. **`load_dotenv()` uses explicit path** to `<project_root>/.env`. Do not switch to implicit loading.
4. **To add a new tool**: create it in `tools/`, import it in `agent/agent.py`, add it to the `tools=[]` list in `build_agent()`, and add a knowledge block to `SYSTEM_PROMPT` in `agent/prompts.py`.
5. **Do not rebuild DuckDB during a coding session.** `powder_oracle.duckdb` is gitignored and only rebuilt via `db/setup.py`.
6. **Every phase is additive.** Do not rewrite existing modules — append to them.

## DuckDB views (for queries)
- `monthly_averages` — resort, month, avg_depth_in, avg_swe_in, avg_daily_new_snow
- `season_summary` — resort, year, peak_depth_in, peak_swe_in, total_new_snow_in
- `traffic_patterns` — corridor, direction, day_of_week, hour, month, is_holiday → avg_volume, stddev_volume

## Module gotchas

### tools/
- Tool functions must accept a **single `str` argument** — LangChain `zero-shot-react-description` requirement. For multi-param tools, accept a comma-separated or JSON string and parse inside.
- Always return a non-empty string. Never return `None`. Return a graceful "no data" message on failure.
- If a live API key is missing (`COTRIP_API_KEY`), return a message telling the agent to fall back to `web_search` — do not raise an exception.
- `get_snowpack_history` routes queries by keyword: `consistent`/`reliable` → STDDEV ranking; `above/below average`/`this season` → year-vs-10yr-avg comparison; default → monthly averages.

### ingestion/
- **SNOTEL API response quirk:** the `/data` endpoint wraps elements under a nested `"data"` key per station. Iterate `station.get("data", [])`, not the top-level list. Do not change this.
- **Alias files:** some resorts share a SNOTEL station (e.g. Breckenridge and A-Basin both use Hoosier Pass `335:CO:SNTL`). The second resort has a `.alias` pointer file in `data/raw/snotel/` instead of a CSV. `db/setup.py` handles these — don't break that logic.
- `cotrip_live.py` returns `None` from `summarise_corridor()` when the API key is absent or the call fails. The tool in `tools/traffic_tools.py` catches `None` and returns a fallback string.
- `cdot_historical.py` generates **synthetic** traffic data — do not replace it with live CDOT API calls without updating `db/setup.py` and the `traffic_patterns` view schema.

### db/
- **Never run `db/setup.py` during a coding session** — it drops and recreates all tables, takes minutes, and `powder_oracle.duckdb` is gitignored anyway.
- Query the **views**, not the raw tables: `monthly_averages`, `season_summary`, `traffic_patterns`.
- To add new data: add a phase block in `setup.py` (load CSV → parquet → table → view). Do not modify existing phases.

### agent/
- Uses `langchain-classic==1.0.1` — a compatibility shim for LangChain 1.x. **Do not upgrade** `langchain` or `langchain-classic` without full regression testing; the agent API changed significantly in 0.2+.
- `SYSTEM_PROMPT` in `prompts.py` is injected as the agent prefix — the LLM sees it before every turn. When adding a tool, always add a corresponding knowledge block here so the agent knows when to reach for it.
- Tool registration order in `build_agent()` influences agent priority. Add new tools at the end of the list unless there is a specific reason to reorder.

## Before requesting a merge (PR checklist)

**AI agents: run through this checklist before creating or suggesting a pull request. Do not open a PR if any applicable item is unchecked.**

### Always
- Verify `streamlit run app.py` starts without errors
- Test at least 2 canonical questions end-to-end (see "Test questions" in this file)
- Confirm no `.env`, `data/`, `*.duckdb`, or `*.parquet` files are staged
- Confirm no relative paths were introduced — all use `Path(__file__).resolve().parent.parent`
- Confirm no system Python was used — conda `powracle` env only

### If a tool was added or modified (`tools/`)
- Tool function accepts a single `str` and always returns a non-empty `str`
- Tool registered in `agent/agent.py` `build_agent()` tools list
- Knowledge block added/updated in `agent/prompts.py` `SYSTEM_PROMPT`
- Tool table updated in root `CLAUDE.md` and `AGENTS.md`

### If a new API or external service was added
- Key name documented in `CLAUDE.md` and `AGENTS.md` under `.env file`
- Graceful fallback implemented when key is absent

### If ingestion was added or changed (`ingestion/`)
- If new data source: new phase block added to `db/setup.py`

### If DuckDB schema or views changed (`db/`)
- `db/setup.py` updated
- PR description explains how the reviewer should rebuild DuckDB locally

### If the UI changed (`app.py`)
- `streamlit run app.py` renders without errors or layout breakage
- Describe what changed and why in the PR description

### Documentation (always update alongside code)
- `CLAUDE.md` and `AGENTS.md` reflect any architectural changes
- Relevant subdirectory `CLAUDE.md` updated if module behaviour changed

