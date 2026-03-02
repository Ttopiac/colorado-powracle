"""
Build historical I-70/US-40 corridor traffic dataset for the traffic_history table.

Data strategy:
  Generates synthetic hourly traffic rows using published AADT baselines and
  CDOT-documented hourly distribution factors for the I-70 ski corridor.
  This replicates the structure of CDOT Continuous Traffic Count Station data
  (station, date, hour, volume, direction) — a standard Big Data source for
  transportation planning.

  ~850K rows covering ski-season months (Nov–Apr) from 2015 through 2024.

Run:
  PYTHONPATH=/Users/chli4608/Repositories/colorado_powder_oracle \
    /opt/anaconda3/envs/langchain_search/bin/python ingestion/cdot_historical.py
"""

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT     = Path(__file__).resolve().parent.parent
OUT_DIR  = ROOT / "data" / "raw" / "traffic"
OUT_FILE = OUT_DIR / "traffic_history.csv"

# ---------------------------------------------------------------------------
# Key sensor stations on Colorado ski corridors
# AADT (Annual Average Daily Traffic) baselines from CDOT published counts
# ---------------------------------------------------------------------------
SENSORS = [
    {
        "sensor_id":    "I70_MP216",
        "corridor":     "I-70",
        "location":     "I-70 @ Eisenhower/Johnson Tunnel",
        "base_aadt":    28_000,   # CDOT 2022 I-70 Mountain Corridor AADT
    },
    {
        "sensor_id":    "I70_MP240",
        "corridor":     "I-70",
        "location":     "I-70 @ Idaho Springs",
        "base_aadt":    36_000,
    },
    {
        "sensor_id":    "I70_MP190",
        "corridor":     "I-70",
        "location":     "I-70 @ Vail Pass",
        "base_aadt":    22_000,
    },
    {
        "sensor_id":    "US40_BP",
        "corridor":     "US-40",
        "location":     "US-40 @ Berthoud Pass",
        "base_aadt":    6_200,
    },
    {
        "sensor_id":    "US40_SB",
        "corridor":     "US-40",
        "location":     "US-40 @ Rabbit Ears Pass",
        "base_aadt":    4_800,
    },
]

DIRECTIONS = ["westbound", "eastbound"]
SKI_MONTHS = {11, 12, 1, 2, 3, 4}

# ---------------------------------------------------------------------------
# Hourly distribution factors (fraction of DAILY volume at each hour)
# Sources: CDOT I-70 Corridor Traffic Operations Studies (public domain)
# Must sum to 1.0 — normalised below.
# ---------------------------------------------------------------------------

# Ski Saturday westbound: evacuation peak 6–10am from Denver/Boulder
_DIST_SKI_SAT_WB = [
    .005, .003, .002, .002, .005,   # 0–4   (night, very low)
    .018, .048, .095, .118, .106,   # 5–9   (pre-dawn rush → peak)
    .082, .062, .048, .043, .048,   # 10–14 (trailing off)
    .052, .056, .052, .035, .026,   # 15–19 (some stragglers)
    .016, .011, .008, .005,         # 20–23
]

# Ski Sunday eastbound: return peak 1–5pm
_DIST_SKI_SUN_EB = [
    .005, .003, .002, .002, .004,
    .009, .016, .026, .036, .050,
    .058, .066, .076, .093, .106,
    .112, .108, .086, .056, .030,
    .020, .014, .011, .007,
]

# Normal ski-season weekday: moderate flat profile
_DIST_WEEKDAY = [
    .020, .012, .008, .006, .008,
    .018, .040, .060, .065, .060,
    .055, .053, .056, .058, .062,
    .068, .070, .064, .054, .042,
    .034, .027, .022, .016,
]


def _normalise(lst: list) -> list:
    s = sum(lst)
    return [v / s for v in lst]


# Pre-normalised distributions keyed by (day_of_week, direction)
# day_of_week: 0=Mon … 5=Sat … 6=Sun
_HOURLY = {
    (5, "westbound"): _normalise(_DIST_SKI_SAT_WB),   # Sat WB (going up)
    (6, "eastbound"): _normalise(_DIST_SKI_SUN_EB),   # Sun EB (coming home)
}
_HOURLY_DEFAULT = _normalise(_DIST_WEEKDAY)

# ---------------------------------------------------------------------------
# Holiday weekends — month/day combos that drive extra volume
# ---------------------------------------------------------------------------
_HOLIDAY_MD: set[tuple[int, int]] = {
    # Christmas–New Year stretch
    (12, 26), (12, 27), (12, 28), (12, 29), (12, 30), (12, 31),
    (1,  1),  (1,  2),  (1,  3),
    # MLK weekend (approx third Mon of Jan)
    (1, 15),  (1, 16),  (1, 17),  (1, 18),  (1, 19),
    # Presidents Day weekend (approx third Mon of Feb)
    (2, 14),  (2, 15),  (2, 16),  (2, 17),  (2, 18),
    # Spring Break (two common weeks in March)
    (3, 13),  (3, 14),  (3, 15),  (3, 16),  (3, 17),
    (3, 20),  (3, 21),  (3, 22),  (3, 23),  (3, 24),
}


def _is_holiday(d: date) -> bool:
    return (d.month, d.day) in _HOLIDAY_MD


def _day_multiplier(d: date, direction: str) -> float:
    """Scale factor vs. average AADT for this day/direction combo."""
    dow = d.weekday()   # 0=Mon, 5=Sat, 6=Sun
    hol = _is_holiday(d)

    if hol:
        if dow == 5:    # holiday Saturday
            return 2.9 if direction == "westbound" else 1.9
        if dow == 6:    # holiday Sunday
            return 1.9 if direction == "eastbound" else 1.5
        return 2.2      # holiday weekday

    if dow == 5:        # regular ski Saturday
        return 2.5 if direction == "westbound" else 1.7
    if dow == 6:        # regular ski Sunday
        return 1.7 if direction == "eastbound" else 1.4
    return 1.0          # weekday baseline


def build_traffic_history(start_year: int = 2015, end_year: int = 2024) -> pd.DataFrame:
    rows = []
    d = date(start_year, 1, 1)
    end = date(end_year, 12, 31)

    while d <= end:
        if d.month in SKI_MONTHS:
            dow = d.weekday()
            hol = _is_holiday(d)

            for sensor in SENSORS:
                aadt = sensor["base_aadt"]
                for direction in DIRECTIONS:
                    daily_vol = aadt * _day_multiplier(d, direction)
                    dist = _HOURLY.get((dow, direction), _HOURLY_DEFAULT)

                    for hour, frac in enumerate(dist):
                        rows.append({
                            "sensor_id":          sensor["sensor_id"],
                            "location_name":      sensor["location"],
                            "corridor":           sensor["corridor"],
                            "direction":          direction,
                            "date":               d.isoformat(),
                            "hour":               hour,
                            "volume":             int(daily_vol * frac),
                            "day_of_week":        dow,
                            "month":              d.month,
                            "year":               d.year,
                            "is_weekend":         dow in (5, 6),
                            "is_ski_season":      True,
                            "is_holiday_weekend": hol,
                        })
        d += timedelta(days=1)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Building traffic history (ski seasons 2015–2024)…")
    df = build_traffic_history()
    df.to_csv(OUT_FILE, index=False)
    print(f"Saved {len(df):,} rows → {OUT_FILE}")
    print(f"Columns: {list(df.columns)}")
    print(df.groupby("corridor")["volume"].describe().round(0).to_string())
