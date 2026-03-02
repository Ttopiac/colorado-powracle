"""
One-time bulk download of 10 years of daily SNOTEL data for each resort.
Run once: python ingestion/snotel_historical.py
"""

import os
from pathlib import Path
import requests
from datetime import date
from resorts import RESORT_STATIONS

ROOT    = Path(__file__).resolve().parent.parent   # project root
RAW_DIR = str(ROOT / "data" / "raw" / "snotel")
START     = "2015-01-01"
BASE_URL  = (
    "https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/"
    "customMultiTimeSeriesGroupByStationReport/daily/start_of_period/"
    "{station}%7Cid%3D%22%22%7Cname/"
    "{start},{end}/"
    "WTEQ%3A%3Avalue%2CSNWD%3A%3Avalue%2CPRCPSA%3A%3Avalue%2CTMAX%3A%3Avalue%2CTMIN%3A%3Avalue"
)


def filename_for(resort_name: str) -> str:
    safe = resort_name.replace("/", "_").replace(" ", "_")
    return os.path.join(RAW_DIR, f"{safe}.csv")


def download_resort(resort_name: str, station_id: str, today: str) -> None:
    url  = BASE_URL.format(station=station_id, start=START, end=today)
    path = filename_for(resort_name)

    if os.path.exists(path):
        print(f"  skipping {resort_name} — file already exists")
        return

    print(f"  downloading {resort_name} ({station_id})...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    with open(path, "w") as f:
        f.write(resp.text)
    lines = resp.text.count("\n")
    print(f"  saved {lines} lines → {path}")


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    today = date.today().isoformat()

    # Deduplicate station IDs (Breckenridge and A-Basin share Hoosier Pass)
    seen_stations = {}
    for resort_name, info in RESORT_STATIONS.items():
        sid = info.get("station_id")
        if not sid:
            print(f"  {resort_name} — no SNOTEL station (skipping)")
            continue
        if sid in seen_stations:
            # Write a symlink-style note so db/setup.py knows which file to use
            primary = seen_stations[sid]
            path = filename_for(resort_name)
            if not os.path.exists(path):
                # Copy primary file path reference into a tiny pointer file
                with open(path + ".alias", "w") as f:
                    f.write(filename_for(primary))
            print(f"  {resort_name} shares station with {primary} — aliased")
        else:
            seen_stations[sid] = resort_name
            download_resort(resort_name, sid, today)

    print("\nDownload complete.")


if __name__ == "__main__":
    main()
