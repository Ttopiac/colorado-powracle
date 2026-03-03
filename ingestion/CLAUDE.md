# ingestion/ — Data Fetching & Pipeline Scripts

## What lives here
Scripts that pull data from external sources and write it to `data/raw/`. The `db/setup.py` script then reads those files to populate DuckDB.

## Scripts

### snotel_live.py — real-time snowpack
**Entry point:** `fetch_current_snowpack(station_triplet: str) -> dict`

Hits the USDA NRCS SNOTEL REST API (`/data` endpoint). No API key required.

**Response quirk (do not change this logic):**
The API wraps element data under a nested `"data"` key per station:
```json
[{"stationTriplet": "...", "data": [{"stationElement": {...}, "values": [...]}]}]
```
The code iterates `station.get("data", [])`. If you see empty results, check the API response structure hasn't changed.

**Elements fetched:** `SNWD` (snow depth, inches) and `WTEQ` (snow water equivalent, inches).
New snow is computed as a delta: `latest_value - value_N_days_ago`, clipped at 0.

**Station IDs:** use the format `XXX:CO:SNTL` (network code is `SNTL`, not `SNOTEL`). All valid IDs are in `resorts.py`.

---

### snotel_historical.py — one-time bulk download
**Run only when `data/raw/snotel/` CSVs are missing.**

Downloads 10 years of daily data (2015-01-01 → today) for each resort in `RESORT_STATIONS`.
Saves to `data/raw/snotel/{resort_name}.csv`.

**Alias files (`.alias`):** Some resorts share a SNOTEL station (e.g., Breckenridge and A-Basin both use Hoosier Pass `335:CO:SNTL`). The second resort gets a `.alias` pointer file instead of a duplicate CSV. `db/setup.py` handles these transparently.

**Run command:**
```bash
PYTHONPATH=/Users/chli4608/Repositories/colorado_powder_oracle \
  /opt/anaconda3/envs/powracle/bin/python ingestion/snotel_historical.py
```

---

### cotrip_live.py — real-time traffic
**Entry points:**
- `fetch_incidents(corridor: str) -> list[dict]`
- `fetch_road_conditions(corridor: str) -> list[dict]`
- `summarise_corridor(corridor: str) -> str` ← what the tool calls

Hits the COtrip REST API. Requires `COTRIP_API_KEY` in `.env`.

**Graceful degradation:** If `COTRIP_API_KEY` is missing or the API call fails, `summarise_corridor()` returns `None`. The tool in `tools/traffic_tools.py` catches this and tells the agent to fall back to `web_search`.

**Valid corridors:** `I-70`, `US-40`, `US-285`, `US-550`

---

### cdot_historical.py — synthetic traffic history generator
**Run only when `data/raw/traffic/traffic_history.csv` is missing.**

Generates ~850K rows of synthetic hourly traffic data for 10 ski seasons (Nov–Apr, 2015–2024) across 5 CDOT sensor locations.

**Sensor locations:**
- I-70 @ Eisenhower Tunnel (westbound peak)
- I-70 @ Vail Pass
- I-70 @ Glenwood Canyon
- US-40 @ Berthoud Pass
- US-40 @ Rabbit Ears Pass

**Key traffic patterns baked in:**
- Saturday westbound peak: 6–10 AM (2.5× baseline AADT)
- Sunday eastbound peak: 1–5 PM (2.5× baseline)
- Holiday multipliers: Christmas (1.8×), MLK/Presidents Day/Spring Break (1.6×)
- Weekday baseline: flat distribution

**Run command:**
```bash
PYTHONPATH=/Users/chli4608/Repositories/colorado_powder_oracle \
  /opt/anaconda3/envs/powracle/bin/python ingestion/cdot_historical.py
```

## Common path pattern
All scripts resolve paths via `Path(__file__).resolve().parent.parent` to locate the project root. Do not change to relative paths — scripts must work from any CWD.

## Data flow summary
```
snotel_historical.py → data/raw/snotel/*.csv ─┐
cdot_historical.py   → data/raw/traffic/*.csv ─┤→ db/setup.py → powder_oracle.duckdb
snotel_live.py       → (direct API, no file)  ─┘   (+ *.parquet intermediates)
cotrip_live.py       → (direct API, no file)
```
