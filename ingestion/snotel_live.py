"""
Fetch current snowpack readings from the SNOTEL REST API.
No API key required.
"""

import requests
from datetime import date, timedelta

SNOTEL_REST = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1"


def fetch_current_snowpack(station_triplet: str) -> dict:
    """
    Returns current snow depth, SWE, and new snow in last 24/48/72 hours.
    Fetches 5 days of data so deltas can be computed even after a missing day.
    """
    start = (date.today() - timedelta(days=5)).isoformat()
    end   = date.today().isoformat()

    try:
        resp = requests.get(
            f"{SNOTEL_REST}/data",
            params={
                "stationTriplets": station_triplet,
                "elements":        "SNWD,WTEQ",
                "beginDate":       start,
                "endDate":         end,
                "duration":        "DAILY",
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()

        # payload is a list of stations; each station has a "data" list of elements
        snwd_values = []
        wteq_values = []

        for station in payload:
            for element_block in station.get("data", []):
                code = element_block.get("stationElement", {}).get("elementCode", "")
                vals = element_block.get("values", [])
                # Each value entry: {"date": "...", "value": float or None}
                numeric = [
                    float(v["value"]) if v["value"] is not None else None
                    for v in vals
                ]
                if code == "SNWD":
                    snwd_values = numeric
                elif code == "WTEQ":
                    wteq_values = numeric

        def latest(lst):
            for v in reversed(lst):
                if v is not None:
                    return v
            return 0.0

        def delta(lst, days):
            non_null = [v for v in lst if v is not None]
            if len(non_null) < days + 1:
                return 0.0
            return max(0.0, non_null[-1] - non_null[-(days + 1)])

        return {
            "snow_depth_in": round(latest(snwd_values), 1),
            "swe_in":        round(latest(wteq_values), 2),
            "new_snow_24h":  round(delta(snwd_values, 1), 1),
            "new_snow_48h":  round(delta(snwd_values, 2), 1),
            "new_snow_72h":  round(delta(snwd_values, 3), 1),
        }

    except Exception as e:
        print(f"  SNOTEL live error for {station_triplet}: {e}")
        return {
            "snow_depth_in": 0.0,
            "swe_in":        0.0,
            "new_snow_24h":  0.0,
            "new_snow_48h":  0.0,
            "new_snow_72h":  0.0,
        }


if __name__ == "__main__":
    # Quick test
    from resorts import RESORT_STATIONS
    for resort, info in list(RESORT_STATIONS.items())[:3]:
        data = fetch_current_snowpack(info["station_id"])
        print(f"{resort}: {data}")
