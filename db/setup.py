"""
Build the DuckDB database from raw SNOTEL CSVs and CDOT traffic data.
Run once (or after re-ingesting data): python db/setup.py

Phase 1: snowpack table + monthly_averages / season_summary views
Phase 2: traffic_history table + traffic_patterns view  ← added here
"""

import os
from pathlib import Path
import duckdb
import pandas as pd
from resorts import RESORT_STATIONS

ROOT            = Path(__file__).resolve().parent.parent   # project root
RAW_DIR         = str(ROOT / "data" / "raw" / "snotel")
PARQUET         = str(ROOT / "data" / "processed" / "snowpack.parquet")
TRAFFIC_CSV     = str(ROOT / "data" / "raw" / "traffic" / "traffic_history.csv")
TRAFFIC_PARQUET = str(ROOT / "data" / "processed" / "traffic.parquet")
DB_PATH         = str(ROOT / "powder_oracle.duckdb")


def safe_filename(resort_name: str) -> str:
    return resort_name.replace("/", "_").replace(" ", "_")


def load_csv(resort_name: str, station_id: str) -> pd.DataFrame | None:
    path = os.path.join(RAW_DIR, f"{safe_filename(resort_name)}.csv")
    alias = path + ".alias"

    # If this resort shares a station with another, use that file
    if not os.path.exists(path) and os.path.exists(alias):
        with open(alias) as f:
            path = f.read().strip()

    if not os.path.exists(path):
        print(f"  missing: {path} — run snotel_historical.py first")
        return None

    # SNOTEL CSVs: comment lines start with #, then a header line, then data
    with open(path) as f:
        lines = f.readlines()

    # Find first non-comment line — that's the header
    data_lines = [l for l in lines if not l.startswith("#")]
    if not data_lines:
        print(f"  empty file: {path}")
        return None

    from io import StringIO
    df = pd.read_csv(StringIO("".join(data_lines)), parse_dates=[0])

    # Normalise column names regardless of SNOTEL's verbose headers
    df.columns = ["date", "swe", "snow_depth", "precip", "tmax", "tmin"]

    df["resort"]     = resort_name
    df["station_id"] = station_id
    df = df.sort_values("date").reset_index(drop=True)

    # Convert to numeric; non-numeric entries (e.g. "N/A") become NaN
    for col in ["swe", "snow_depth", "precip", "tmax", "tmin"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Derived columns
    df["new_snow_24h"] = df["snow_depth"].diff(1).clip(lower=0)
    df["new_snow_48h"] = df["snow_depth"].diff(2).clip(lower=0)
    df["new_snow_72h"] = df["snow_depth"].diff(3).clip(lower=0)
    df["month"]        = df["date"].dt.month
    df["year"]         = df["date"].dt.year

    return df


def build():
    os.makedirs(ROOT / "data" / "processed", exist_ok=True)

    frames = []
    for resort_name, info in RESORT_STATIONS.items():
        print(f"Loading {resort_name}...")
        df = load_csv(resort_name, info["station_id"])
        if df is not None:
            frames.append(df)

    if not frames:
        print("No data loaded. Aborting.")
        return

    combined = pd.concat(frames, ignore_index=True)
    combined.to_parquet(PARQUET, index=False)
    print(f"\nSaved {len(combined):,} rows → {PARQUET}")

    con = duckdb.connect(DB_PATH)
    con.execute("DROP TABLE IF EXISTS snowpack")
    con.execute(f"""
        CREATE TABLE snowpack AS
        SELECT * FROM read_parquet('{PARQUET}')
    """)

    con.execute("""
        CREATE OR REPLACE VIEW monthly_averages AS
        SELECT
            resort,
            month,
            ROUND(AVG(snow_depth), 1)   AS avg_depth_in,
            ROUND(AVG(swe), 2)          AS avg_swe_in,
            ROUND(AVG(new_snow_24h), 1) AS avg_daily_new_snow
        FROM snowpack
        WHERE snow_depth IS NOT NULL
        GROUP BY resort, month
        ORDER BY resort, month
    """)

    con.execute("""
        CREATE OR REPLACE VIEW season_summary AS
        SELECT
            resort,
            year,
            ROUND(MAX(snow_depth), 1)   AS peak_depth_in,
            ROUND(MAX(swe), 2)          AS peak_swe_in,
            ROUND(SUM(new_snow_24h), 1) AS total_new_snow_in
        FROM snowpack
        WHERE month IN (11, 12, 1, 2, 3, 4)
          AND snow_depth IS NOT NULL
        GROUP BY resort, year
        ORDER BY resort, year
    """)

    # Quick sanity check
    row_count = con.execute("SELECT COUNT(*) FROM snowpack").fetchone()[0]
    resort_count = con.execute("SELECT COUNT(DISTINCT resort) FROM snowpack").fetchone()[0]
    print(f"Snowpack table ready: {row_count:,} rows across {resort_count} resorts → {DB_PATH}")
    con.close()


# ── Phase 2: traffic table + traffic_patterns view ────────────────────────────

def build_traffic():
    if not os.path.exists(TRAFFIC_CSV):
        print(f"Missing {TRAFFIC_CSV} — run ingestion/cdot_historical.py first")
        return

    os.makedirs(ROOT / "data" / "processed", exist_ok=True)

    print("Loading traffic history…")
    df = pd.read_csv(TRAFFIC_CSV, parse_dates=["date"])
    df.to_parquet(TRAFFIC_PARQUET, index=False)
    print(f"Saved {len(df):,} rows → {TRAFFIC_PARQUET}")

    con = duckdb.connect(DB_PATH)
    con.execute("DROP TABLE IF EXISTS traffic_history")
    con.execute(f"""
        CREATE TABLE traffic_history AS
        SELECT * FROM read_parquet('{TRAFFIC_PARQUET}')
    """)

    con.execute("""
        CREATE OR REPLACE VIEW traffic_patterns AS
        SELECT
            corridor,
            location_name,
            direction,
            day_of_week,
            hour,
            month,
            is_holiday_weekend,
            ROUND(AVG(volume), 0)    AS avg_volume,
            ROUND(STDDEV(volume), 0) AS stddev_volume,
            COUNT(*)                 AS sample_size
        FROM traffic_history
        WHERE is_ski_season = TRUE
        GROUP BY ALL
        ORDER BY corridor, direction, day_of_week, hour
    """)

    row_count = con.execute("SELECT COUNT(*) FROM traffic_history").fetchone()[0]
    print(f"Traffic table ready: {row_count:,} rows → {DB_PATH}")
    con.close()


if __name__ == "__main__":
    build()
    build_traffic()
