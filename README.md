# ⛷️ Colorado Powracle

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Colorado Powracle** is an AI-powered ski conditions assistant that answers real natural-language questions about Colorado ski resorts — backed by live snowpack sensors, 10 years of historical data, and real-time web search.

Unlike general-purpose AI assistants (ChatGPT, Gemini, Claude), Colorado Powracle doesn't guess or hallucinate snow conditions. Every answer is grounded in actual data pulled at the moment you ask.

---

## [Demo Video](https://www.youtube.com/watch?v=9hb8qsD4CKA)

[![Colorado Powracle Demo](https://img.youtube.com/vi/9hb8qsD4CKA/maxresdefault.jpg?v=2)](https://www.youtube.com/watch?v=9hb8qsD4CKA)

---

## Installation & Setup

### 1. Clone the repo

```bash
git clone https://github.com/Ttopiac/colorado-powracle.git
cd colorado-powracle
```

### 2. Create a Python environment

```bash
conda create -n powracle python=3.11 -y
conda activate powracle
pip install -r requirements.txt
```

### 3. Get your API keys

You need three API keys. All have free tiers sufficient for personal use.

| Service | Purpose | Sign up at |
|---------|---------|-----------|
| **OpenRouter** | Routes requests to the Claude 3 Haiku LLM | [openrouter.ai](https://openrouter.ai) → Keys → Create Key |
| **SerpAPI** | Live Google search (lift status, road conditions) | [serpapi.com](https://serpapi.com) → Dashboard → API Key |
| **COtrip** | Live Colorado road conditions & chain laws (optional) | [manage-api.cotrip.org](https://manage-api.cotrip.org/login) → Register → My Account → API Key |

> COtrip is optional — if omitted, road condition questions fall back to web search automatically.

### 4. Create your `.env` file

Create a file named `.env` in the project root (this file is gitignored — never commit it):

```
OPENROUTER_API_KEY=sk-or-your-key-here
SERPAPI_API_KEY=your-serpapi-key-here
COTRIP_API_KEY=your-cotrip-key-here
```

### 5. Download historical snow data

Downloads 10 years of daily SNOTEL readings for all 19 resorts (~3 MB, takes ~2 minutes). Run once.

```bash
PYTHONPATH=. python ingestion/snotel_historical.py
```

### 6. Generate historical traffic data

Builds 10 years of ski-season traffic patterns for I-70 and US-40 corridors (~850K rows) from published CDOT baselines. Run once.

```bash
PYTHONPATH=. python ingestion/cdot_historical.py
```

### 7. Build the local database

Loads both the snow CSVs and traffic CSV into DuckDB. Run once (or again after re-running either ingestion script).

```bash
PYTHONPATH=. python db/setup.py
```

### 8. Launch the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

> **Why isn't the data included in the repo?**
> All data files are excluded from git (~46 MB total) because they are fully regenerable. Steps 5–7 above recreate them in under 5 minutes using free public sources. No account or payment is needed for the snow or traffic data.

---

## What Makes It Different

| | Colorado Powracle | ChatGPT / Gemini / Claude |
|---|---|---|
| Live snow depth & new snow | ✅ Real-time SNOTEL sensors | ❌ No live data |
| 10-year historical snowpack | ✅ 40,780 rows in DuckDB | ❌ Generic knowledge only |
| Resort-specific routing | ✅ I-70, US-40, US-550, etc. | ❌ Vague at best |
| Above/below average season | ✅ Compares current vs. historical | ❌ Cannot compute |
| Pass filtering (IKON/EPIC/INDY) | ✅ Built in | ❌ Not applicable |
| Lift & road status | ✅ Live web search | ⚠️ May be outdated |

---

## How to Run

```bash
conda activate powracle
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

---

## API (FastAPI)

In addition to the Streamlit app, Colorado Powracle now exposes the LangChain chat agent through a small FastAPI service.

### Run the API

From the project root, with the conda environment active:

```bash
conda activate powracle
uvicorn api:app --reload
```

Then open:

- API root: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Endpoints

- `GET /health` — simple health check
- `POST /chat` — send a question and receive an answer plus ranking

### Example request

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which resort has the most fresh snow right now?",
    "messages": [],
    "selected_passes": ["All"],
    "start_city": "Denver"
  }'
```

### Example response

```json
{
  "answer": "Loveland currently has the deepest base depth...",
  "ranking": ["Loveland", "Ski Cooper", "Winter Park"],
  "raw_response": "..."
}
```

---

## The Interface

### Left Panel — Live Conditions
- **My pass(es):** Filter resorts to only those on your IKON, EPIC, or INDY pass.
- **Starting from:** Select your departure city (Denver, Boulder, Colorado Springs, etc.) to see drive distances.
- **Sort by:** Order resorts by Fresh Snow (72h), Base Depth, Distance, or let the AI pick for you.
- **Today's Leaders:** Banner highlighting the resort with the most fresh snow, deepest base, and closest powder (6"+).
- **Quick Filters:** Checkbox chips to narrow the list — 6"+ powder, 50"+ base, <100mi, 4"+ weekend forecast.
- **Snowfall Effect:** Toggle a CSS snowfall animation for ambiance.
- Each resort card shows a colored dot (white = low snow → deep blue = deep snow), new snow in the last 72 hours, base depth, and drive distance.

### Map (collapsible)
Click **Show Resort Map** to open an interactive map of all resorts. Dot color encodes snow level. Dot ring color encodes pass type (blue = IKON, purple = EPIC, green = INDY). Hover over any dot for details.

### Smart Trip Planner (collapsible)
Plan a multi-day ski trip: pick a start date, number of days (1–7), lodging preference, and any notes. The AI generates a day-by-day itinerary with resort recommendations, forecasted snow, drive times, and departure timing.

### Right Panel — Ask the Oracle
Type any ski-related question in plain English. The Oracle calls its tools, consults real data, and returns a grounded answer with specific numbers.

---

## Example Questions & Answers

---

### 🌨️ "Where has the most new snow in the last 72 hours?"

**ChatGPT / Gemini / Claude:**
> "I don't have access to real-time snowfall data. I'd recommend checking ski resort websites or apps like OnTheSnow for current conditions."

**Colorado Powracle:**
> "Based on live SNOTEL sensor data, Wolf Creek leads with **18 inches** of new snow in the last 72 hours, followed by Telluride at **11 inches** and Crested Butte at **9 inches**. Wolf Creek is on the INDY Pass and is ~230 miles from Denver via US-160."

---

### 📅 "Which Colorado resort historically gets the most snow in January?"

**ChatGPT / Gemini / Claude:**
> "Wolf Creek is generally considered one of Colorado's snowiest resorts, receiving around 400+ inches annually. Telluride and Crested Butte also tend to get heavy snowfall."

**Colorado Powracle:**
> "Looking at 10 years of SNOTEL data, **Wolf Creek** averages **58 inches** of snowpack in January, making it the snowiest in the state. Crested Butte follows at **47 inches**, and Telluride at **44 inches**. January is peak season at all three — well above the statewide average of 31 inches."

---

### 📊 "Is this ski season above or below average at Steamboat?"

**ChatGPT / Gemini / Claude:**
> "I don't have access to current season data. You can check the Steamboat Springs resort website or the NRCS SNOTEL site for up-to-date snowpack information."

**Colorado Powracle:**
> "The Dry Lake SNOTEL station near Steamboat is currently showing **62 inches** of snow water equivalent. The 10-year January average at that station is **54 inches**, so this season is running **15% above average** — one of the better starts to a season in recent memory."

---

### 🚗 "I want to avoid I-70 this weekend — where should I ski?"

**ChatGPT / Gemini / Claude:**
> "If you want to avoid I-70, you could consider resorts in southern Colorado like Wolf Creek or Telluride, which are accessible via US-160 or US-550."

**Colorado Powracle:**
> "Good call — I-70 can be brutal on weekends. Your best options right now that skip I-70 entirely:
> - **Wolf Creek** (US-160) — **18\" new in 72h**, deepest base in the state at 94\". Long drive (~4h from Denver) but worth it.
> - **Steamboat** (US-40) — **6\" new in 72h**, solid 72\" base. About 3h from Denver, much lighter traffic.
> - **Monarch Mountain** (US-50) — **4\" new**, 68\" base, INDY Pass. Quiet, uncrowded, ~3.5h from Denver.
> Skip Breckenridge, Vail, Keystone, and Copper this weekend if traffic is a concern."

---

### 🏆 "Which resort is most consistent year over year?"

**ChatGPT / Gemini / Claude:**
> "Resorts like Vail and Breckenridge are generally considered reliable due to their snowmaking capabilities and consistent annual snowfall."

**Colorado Powracle:**
> "Analyzing variance across 10 seasons of SNOTEL data, **Wolf Creek** has the lowest coefficient of variation (12%) — meaning it delivers dependable snowpack regardless of whether the year is wet or dry. **Steamboat** is second most consistent (18%). **Arapahoe Basin** has the highest variance (34%) — great in strong years, thin in weak ones."

---

## Data Sources

| Source | Tool | Data | Refresh |
|--------|------|------|---------|
| [USDA NRCS SNOTEL REST API](https://wcc.sc.egov.usda.gov/awdbRestApi) | `get_current_snowpack` | Live snow depth, SWE, new snow 24/48/72h | Every 30 min |
| SNOTEL Historical CSVs → Parquet → DuckDB | `get_snowpack_history` | 10 years of daily snowpack, monthly averages, season summaries | Static (2015–2024) |
| SerpAPI web search | `web_search` | Lift status, forecasts, general fallback | Real-time |
| [COtrip REST API](https://manage-api.cotrip.org/login) (Colorado DOT) | `get_live_traffic` | Live road incidents, chain laws, surface conditions | Real-time |
| CDOT Historical Traffic → DuckDB | `get_best_departure_time` | 10 years of hourly traffic volumes on I-70, US-40, US-285 | Static |
| [Open-Meteo API](https://open-meteo.com/) | `get_snow_forecast` | 7-day snowfall forecast (HRRR model, no key required) | Real-time |

---

## Supported Resorts

| Resort | Pass | Corridor |
|--------|------|----------|
| Steamboat Springs | IKON | US-40 |
| Winter Park | IKON | US-40 |
| Copper Mountain | IKON | I-70 |
| Arapahoe Basin | IKON | I-70 |
| Aspen / Snowmass | IKON | I-70 → CO-82 |
| Eldora | IKON | CO-119 |
| Breckenridge | EPIC | I-70 |
| Vail | EPIC | I-70 |
| Beaver Creek | EPIC | I-70 |
| Keystone | EPIC | I-70 |
| Crested Butte | EPIC | US-285 → CO-135 |
| Telluride | EPIC | US-285 → US-550 |
| Loveland | INDY | I-70 |
| Wolf Creek | INDY | US-160 |
| Monarch Mountain | INDY | US-50 |
| Ski Cooper | INDY | US-24 |
| Purgatory | INDY | US-550 |
| Powderhorn | INDY | I-70 → CO-65 |
| Sunlight Mountain | INDY | I-70 → CO-82 |

---

## Tech Stack

- **Agent**: LangChain `zero-shot-react-description`
- **LLM**: `claude-3-haiku` via OpenRouter
- **Live snow data**: USDA NRCS SNOTEL REST API (no key required)
- **Historical snow data**: Apache Parquet + DuckDB (40,780 rows, 2015–2024)
- **Live road conditions**: COtrip REST API (Colorado DOT)
- **Historical traffic data**: CDOT traffic volumes → DuckDB
- **Snow forecast**: Open-Meteo API (HRRR model, no key required)
- **Web search**: SerpAPI
- **UI**: Streamlit + Plotly
- **Map tiles**: ESRI World Topo Map
