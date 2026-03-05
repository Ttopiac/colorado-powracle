"""
LangChain tool: get_snow_forecast
7-day snowfall forecast for a named Colorado ski resort via Open-Meteo (no key required).
"""

from datetime import date, timedelta
from langchain_classic.tools import Tool
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from resorts import RESORT_STATIONS
from ingestion.openmeteo_forecast import fetch_snow_forecast


def _get_snow_forecast(resort_name: str) -> str:
    # Fuzzy match resort name
    key = None
    name_lower = resort_name.lower().strip()
    for r in RESORT_STATIONS:
        if name_lower in r.lower() or r.lower() in name_lower:
            key = r
            break
    if key is None:
        return (
            f"Resort '{resort_name}' not found. "
            f"Known resorts: {', '.join(RESORT_STATIONS.keys())}"
        )

    info = RESORT_STATIONS[key]
    try:
        forecast = fetch_snow_forecast(info["lat"], info["lon"], days=7)
    except Exception as e:
        return f"Could not fetch forecast for {key}: {e}"

    today = date.today()
    days_to_sat = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_to_sat)
    sunday = saturday + timedelta(days=1)
    sat_str = saturday.isoformat()
    sun_str = sunday.isoformat()

    lines = [f"📅 7-day snowfall forecast for {key}:"]
    weekend_total = 0.0
    for d in forecast:
        snow = d["snowfall_in"]
        tmax = d["temp_max_f"]
        tmin = d["temp_min_f"]
        day_label = date.fromisoformat(d["date"]).strftime("%a %b %d")
        marker = ""
        if d["date"] == sat_str:
            marker = "  ⛷️ Saturday"
            weekend_total += snow
        elif d["date"] == sun_str:
            marker = "  ⛷️ Sunday"
            weekend_total += snow
        temp = f"  (high {tmax:.0f}°F / low {tmin:.0f}°F)" if tmax is not None else ""
        lines.append(f"  {day_label}: {snow:.1f}\"{marker}{temp}")

    lines.append(f"\n  Weekend total: {weekend_total:.1f}\" expected")
    lines.append("  (Source: NOAA HRRR model via Open-Meteo. Estimates only — check OpenSnow for expert forecasts.)")
    return "\n".join(lines)


snow_forecast_tool = Tool(
    name="get_snow_forecast",
    func=_get_snow_forecast,
    description=(
        "Returns a 7-day snowfall forecast for a named Colorado ski resort using Open-Meteo (no key required). "
        "Use this when the user asks about conditions this weekend, upcoming snow, or future powder. "
        "Input: resort name (e.g. 'Steamboat Springs'). "
        "Output: daily snowfall in inches for the next 7 days, with weekend days highlighted and a weekend total."
    ),
)
