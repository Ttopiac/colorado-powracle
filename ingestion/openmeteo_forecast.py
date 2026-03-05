"""
Fetch snowfall forecasts from Open-Meteo (no API key required).
https://open-meteo.com/

Endpoints used:
  GET /v1/forecast — daily snowfall_sum, temperature_2m_max, temperature_2m_min
Snowfall is returned in cm and converted to inches here.

Model: tries HRRR (High-Resolution Rapid Refresh, NOAA) at 3km grid first for
best mountain accuracy. HRRR only supports ~48h, so if it returns an error
(e.g. forecast_days=7), falls back to Open-Meteo best_match automatically.

Note: forecasts will differ from specialized services like OpenSnow, which apply
expert meteorologist post-processing on top of model output.
Treat these numbers as model estimates, not guarantees.
"""

from datetime import date, timedelta
import requests

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_snow_forecast(lat: float, lon: float, days: int = 7) -> list[dict]:
    """
    Returns daily snowfall forecast for the given coordinates.
    Snowfall in inches, temperatures in °F.
    Tries HRRR (3km resolution) first; falls back to Open-Meteo best_match if unavailable.
    """
    base_params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "snowfall_sum,temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "timezone": "America/Denver",
        "forecast_days": days,
    }

    # Try HRRR first (3km resolution, better for mountain terrain)
    r = requests.get(OPENMETEO_URL, params={**base_params, "models": "hrrr"}, timeout=10)
    if not r.ok:
        # HRRR only covers ~48h — fall back to Open-Meteo best_match for 7-day window
        r = requests.get(OPENMETEO_URL, params=base_params, timeout=10)
    r.raise_for_status()
    data = r.json()["daily"]

    results = []
    for i, date_str in enumerate(data["time"]):
        snow_cm = data["snowfall_sum"][i] or 0
        results.append({
            "date": date_str,
            "snowfall_in": round(snow_cm * 0.3937, 1),
            "temp_max_f": data["temperature_2m_max"][i],
            "temp_min_f": data["temperature_2m_min"][i],
        })
    return results


def get_weekend_snowfall(lat: float, lon: float) -> dict:
    """
    Returns expected snowfall (inches) for the upcoming Saturday and Sunday.
    """
    today = date.today()
    days_to_sat = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_to_sat)
    sunday = saturday + timedelta(days=1)

    forecast = fetch_snow_forecast(lat, lon, days=7)
    sat_str = saturday.isoformat()
    sun_str = sunday.isoformat()

    sat_snow = next((d["snowfall_in"] for d in forecast if d["date"] == sat_str), 0.0)
    sun_snow = next((d["snowfall_in"] for d in forecast if d["date"] == sun_str), 0.0)

    return {
        "saturday": sat_str,
        "sunday": sun_str,
        "saturday_snow_in": sat_snow,
        "sunday_snow_in": sun_snow,
        "weekend_total_in": round(sat_snow + sun_snow, 1),
    }
