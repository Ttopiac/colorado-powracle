# Colorado Powracle — Claude Context

## What this project is
A LangChain-powered ski conditions agent with a Streamlit UI.
A skier asks a natural-language question → the agent calls real tools → returns a grounded answer.

GitHub: https://github.com/Ttopiac/colorado-powracle (private, MIT license)

Built as a Big Data Architecture project using:
- **Live snow data**: USDA NRCS SNOTEL REST API (no key required)
- **Live traffic data**: COtrip REST API (requires `COTRIP_API_KEY`)
- **Historical snow data**: 10 years of daily SNOTEL CSVs → Apache Parquet → DuckDB (40,780 rows)
- **Historical traffic data**: 10yr CDOT hourly volumes → DuckDB `traffic_patterns` view
- **Agent**: LangChain `zero-shot-react-description` via `langchain-classic` (compatibility layer for LangChain 1.x)
- **LLM**: `anthropic/claude-3-haiku` via OpenRouter
- **UI**: Streamlit with Plotly Scattermapbox (ESRI World Topo Map tiles), Mountain Stone theme (`#383f4a` / `#424e5c`)
- **API**: FastAPI (`api.py`) exposes the same chat agent via `POST /chat` and `GET /health`

## How to run
### Streamlit UI
```bash
conda activate powracle   # always use this env
cd /Users/chli4608/Repositories/colorado_powder_oracle
streamlit run app.py
```

### FastAPI API
```bash
conda activate powracle
uvicorn api:app --reload
# Docs at http://127.0.0.1:8000/docs
```

## Key decisions & fixes made during setup

### Station IDs
SNOTEL network code is `SNTL`, NOT `SNOTEL`. All IDs in `resorts.py` use `:CO:SNTL`.
Correct IDs confirmed via `https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/stations`.

### SNOTEL REST API response structure
The `/data` endpoint wraps elements under a `"data"` key per station:
```json
[{"stationTriplet": "...", "data": [{"stationElement": {...}, "values": [...]}]}]
```
Fixed in `ingestion/snotel_live.py` (iterates `station.get("data", [])`).

### Absolute paths
All scripts use `Path(__file__).resolve().parent.parent` for paths — they work from any CWD.
Do NOT change to relative paths.

### .env loading
`load_dotenv()` uses explicit path: `Path(__file__).resolve().parent.parent / ".env"`.
The `.env` file lives at the project root (gitignored).
Required keys: `OPENROUTER_API_KEY`, `SERPAPI_API_KEY`, `COTRIP_API_KEY`

### Conda env
All Python must run under `/opt/anaconda3/envs/powracle/bin/python`.
Do NOT use system Python or base Anaconda.

## The 6 tools
| Tool | Source | Description |
|------|--------|-------------|
| `get_current_snowpack` | SNOTEL REST API (live) | Snow depth, SWE, new snow 24/48/72h |
| `get_snowpack_history` | DuckDB (10yr historical) | Monthly averages, season summary, consistency |
| `web_search` | SerpAPI | Lift status, road conditions, forecasts |
| `get_live_traffic` | COtrip REST API (live) | Road incidents, chain laws, corridor conditions |
| `get_best_departure_time` | DuckDB `traffic_patterns` view (10yr historical) | Best departure windows by corridor and day of week |
| `get_snow_forecast` | Open-Meteo API (no key required) | 7-day snowfall forecast in inches, weekend totals highlighted |

## UI details
- Map: Plotly Scattermapbox with ESRI World Topo Map tiles
- Two-layer markers: halo (pass color) + fill (snow colorscale)
- Collapsible map expander, 2-column layout (conditions | chat)
- Sort options: Fresh Snow / Base Snow / Distance / AI Pick
- Snowfall toggle: CSS snowflake animation, toggled via checkbox in header (uses `@st.fragment` to avoid full page rerun)
- Today's Leaders banner: shows most fresh snow, best base depth, and closest powder resort (6"+)
- Quick filter chips: 4 checkboxes to filter resort list — 6"+ powder (72h), 50"+ base, <100mi distance, 4"+ weekend forecast. Logic lives in `_apply_quick_filters()`.
- Smart Trip Planner: collapsible expander with date picker, day slider (1–7), lodging preference, and notes. Generates a multi-day itinerary prompt sent to the agent. Uses `load_7day_forecasts()` (cached 3hr) for full 7-day Open-Meteo forecast, and injects distances + traffic tips into the agent context.
- Deterministic answers toggle: optional checkbox that answers simple factual live-data questions (most fresh snow, deepest base) directly from SNOTEL data without calling the LLM. Logic in `agent/deterministic_answers.py`.
- Theme: Mountain Stone (`#383f4a` / `#424e5c`)

## Evaluation
- `eval/prompts.csv` — 30 benchmark prompts (10 factual, 10 recommendation, 10 explanatory) with expected answer type (deterministic vs agent)

## Extension roadmap
- Phase 2: Traffic — DONE (`tools/traffic_tools.py`, `ingestion/cdot_historical.py`, `ingestion/cotrip_live.py`)
- Phase 3: Location — `tools/location_tools.py`, `ingestion/location.py`
  - Add `OPENROUTESERVICE_API_KEY` to `.env`
- Phase 4: UI upgrades — `app.py` (UI changes are open; theme and layout may evolve freely)

Every phase is additive. No existing files need to be rewritten.

## Running one-off data commands
```bash
# Re-download historical snow data (only if CSVs are missing)
PYTHONPATH=/Users/chli4608/Repositories/colorado_powder_oracle \
  /opt/anaconda3/envs/powracle/bin/python ingestion/snotel_historical.py

# Generate historical traffic data
PYTHONPATH=/Users/chli4608/Repositories/colorado_powder_oracle \
  /opt/anaconda3/envs/powracle/bin/python ingestion/cdot_historical.py

# Rebuild DuckDB (only if powder_oracle.duckdb is missing)
PYTHONPATH=/Users/chli4608/Repositories/colorado_powder_oracle \
  /opt/anaconda3/envs/powracle/bin/python db/setup.py

# Quick live data check
PYTHONPATH=/Users/chli4608/Repositories/colorado_powder_oracle \
  /opt/anaconda3/envs/powracle/bin/python -c "
from ingestion.snotel_live import fetch_current_snowpack
print(fetch_current_snowpack('457:CO:SNTL'))
"
```

## Test questions (canonical)
```
Where has the most new snow in the last 72 hours?
Which Colorado resort historically gets the most snow in January?
Is this ski season above or below average at Steamboat?
Which resort is most consistent year over year?
Where should I ski this weekend for powder?
I want to avoid I-70 — which powder resort should I consider?
What is the current road conditions on I-70 heading to the mountains?
When is the best time to leave Denver on a Saturday to beat traffic to Vail?
Which resort is forecasted to get the most snow this weekend?
How much snow is expected at Wolf Creek this Saturday?
```
