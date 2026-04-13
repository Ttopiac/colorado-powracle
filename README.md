# ⛷️ Colorado Powracle

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An AI-powered ski conditions assistant for Colorado. Ask natural-language questions about snow, traffic, and trip planning — every answer is grounded in live sensor data and 10 years of historical records, not LLM guesses.

## [Demo Video](https://www.youtube.com/watch?v=9hb8qsD4CKA)
## [User Management Demo Video] (https://www.youtube.com/watch?v=sAVDxx9mR_g)

[![Colorado Powracle Demo](https://img.youtube.com/vi/9hb8qsD4CKA/maxresdefault.jpg?v=2)](https://www.youtube.com/watch?v=9hb8qsD4CKA)

## Why not just ask ChatGPT?

| | Colorado Powracle | ChatGPT / Gemini / Claude |
|---|---|---|
| Live snow depth & new snow | ✅ Real-time SNOTEL sensors | ❌ No live data |
| 10-year historical snowpack | ✅ 40,780 rows in DuckDB | ❌ Generic knowledge only |
| Above/below average season | ✅ Compares current vs. historical | ❌ Cannot compute |
| Traffic & departure planning | ✅ Live COtrip + 10yr patterns | ❌ Vague at best |
| 7-day snowfall forecast | ✅ Open-Meteo HRRR model | ❌ May be outdated |
| Pass filtering (IKON/EPIC/INDY) | ✅ Built in | ❌ Not applicable |

## Quick Start

```bash
git clone https://github.com/Ttopiac/colorado-powracle.git
cd colorado-powracle
conda create -n powracle python=3.11 -y
conda activate powracle
pip install -r requirements.txt
```

Set up your `.env` with API keys, download data, and build the database — full steps in **[docs/SETUP.md](docs/SETUP.md)**.

Then launch:
```bash
streamlit run app.py        # UI at http://localhost:8501
uvicorn api:app --reload    # API docs at http://localhost:8000/docs
```

## Tools

The agent has 6 tools it can call based on your question:

| Tool | Source | What it returns |
|------|--------|-----------------|
| `get_current_snowpack` | SNOTEL REST API | Live snow depth, SWE, new snow 24/48/72h |
| `get_snowpack_history` | DuckDB (10yr) | Monthly averages, season comparisons, consistency |
| `get_snow_forecast` | Open-Meteo API | 7-day snowfall forecast |
| `get_live_traffic` | COtrip REST API | Road incidents, chain laws, surface conditions |
| `get_best_departure_time` | DuckDB (10yr) | Best departure windows by corridor and day |
| `web_search` | SerpAPI | Lift status, road conditions, general fallback |

## 19 Supported Resorts

**IKON:** Steamboat Springs, Winter Park, Copper Mountain, Arapahoe Basin, Aspen / Snowmass, Eldora
**EPIC:** Breckenridge, Vail, Beaver Creek, Keystone, Crested Butte, Telluride
**INDY:** Loveland, Wolf Creek, Monarch Mountain, Ski Cooper, Purgatory, Powderhorn, Sunlight Mountain

## Tech Stack

LangChain `zero-shot-react-description` agent · Claude 3 Haiku via OpenRouter · USDA SNOTEL REST API · COtrip REST API · Open-Meteo API · SerpAPI · DuckDB · PostgreSQL + SQLAlchemy · Streamlit + Plotly · FastAPI

## Docs

- **[Full Setup Guide](docs/SETUP.md)** — API keys, data ingestion, PostgreSQL, FastAPI
- **[Contributor Onboarding](docs/ONBOARDING.md)** — branch workflow, PR process, AI assistant setup

## License

MIT — see [LICENSE](LICENSE).
