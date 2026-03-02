"""
Fetch live Colorado road conditions and incidents from the COTRIP data API.

Requires COTRIP_API_KEY in .env (free registration at https://data.cotrip.org/).
Falls back gracefully when no key is present — caller should use web_search instead.

COTRIP API docs: https://data.cotrip.org/
Endpoints used:
  GET /api/v1/incidents      — active accidents, closures, road work
  GET /api/v1/roadConditions — surface conditions, chain laws, traction advisories
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

COTRIP_BASE = "https://data.cotrip.org/api/v1"
_API_KEY    = os.getenv("COTRIP_API_KEY", "")

# Corridor name → route strings that appear in COTRIP responses
CORRIDOR_ROUTES: dict[str, list[str]] = {
    "I-70":   ["I-70", "I70", "Interstate 70"],
    "US-40":  ["US-40", "US40", "US 40"],
    "US-285": ["US-285", "US285", "US 285"],
    "US-550": ["US-550", "US550"],
    "CO-82":  ["CO-82", "CO82", "Highway 82"],
}

_TIMEOUT = 8   # seconds per request


def _get(endpoint: str) -> dict | None:
    """Hit a COTRIP endpoint; return parsed JSON or None on failure."""
    if not _API_KEY:
        return None
    try:
        r = requests.get(
            f"{COTRIP_BASE}/{endpoint}",
            params={"apiKey": _API_KEY},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _route_matches(route_str: str, corridor: str) -> bool:
    aliases = CORRIDOR_ROUTES.get(corridor, [corridor])
    return any(alias.lower() in route_str.lower() for alias in aliases)


def _extract_text(prop: dict, keys: list[str]) -> str:
    for k in keys:
        v = prop.get(k, "")
        if v:
            return str(v)
    return ""


def fetch_incidents(corridor: str) -> list[dict]:
    """
    Return active incidents on the given corridor.
    Each dict has: type, description, direction, start_time.
    Returns [] if no API key or API is unreachable.
    """
    data = _get("incidents")
    if not data:
        return []

    features = data.get("features") or data.get("data") or []
    results = []
    for feat in features:
        prop = feat.get("properties", {}) if isinstance(feat, dict) else feat
        route = _extract_text(prop, ["route", "routeName", "roadway", "highway"])
        if not _route_matches(route, corridor):
            continue
        results.append({
            "type":        _extract_text(prop, ["type", "eventType", "incidentType"]),
            "description": _extract_text(prop, ["description", "headline", "summary"]),
            "direction":   _extract_text(prop, ["direction", "travelDirection"]),
            "start_time":  _extract_text(prop, ["startTime", "start_time", "createdDate"]),
        })
    return results


def fetch_road_conditions(corridor: str) -> list[dict]:
    """
    Return road surface conditions and traction laws on the given corridor.
    Each dict has: location, surface_condition, traction, direction.
    Returns [] if no API key or API is unreachable.
    """
    data = _get("roadConditions")
    if not data:
        return []

    features = data.get("features") or data.get("data") or []
    results = []
    for feat in features:
        prop = feat.get("properties", {}) if isinstance(feat, dict) else feat
        route = _extract_text(prop, ["stateRoute", "route", "routeName", "roadway"])
        if not _route_matches(route, corridor):
            continue
        results.append({
            "location":          _extract_text(prop, ["locationDescription", "location", "description"]),
            "surface_condition": _extract_text(prop, ["surfaceCondition", "roadCondition", "condition"]),
            "traction":          _extract_text(prop, ["tractionLaw", "traction", "chainLaw"]),
            "direction":         _extract_text(prop, ["direction", "travelDirection"]),
        })
    return results


def summarise_corridor(corridor: str) -> str:
    """
    Return a human-readable summary of current conditions on a corridor.
    Returns None if no API key is configured (caller should fall back to web_search).
    """
    if not _API_KEY:
        return None

    incidents   = fetch_incidents(corridor)
    conditions  = fetch_road_conditions(corridor)

    lines = [f"Live {corridor} conditions (COTRIP):"]

    if incidents:
        lines.append(f"\nIncidents ({len(incidents)}):")
        for inc in incidents[:5]:    # cap at 5 to avoid prompt bloat
            desc = inc["description"] or inc["type"] or "incident"
            d    = f" [{inc['direction']}]" if inc["direction"] else ""
            lines.append(f"  • {desc}{d}")
    else:
        lines.append("\nNo active incidents reported.")

    if conditions:
        chain_laws = [c for c in conditions if c["traction"]]
        if chain_laws:
            lines.append(f"\nTraction/chain laws active ({len(chain_laws)} segments):")
            for c in chain_laws[:3]:
                loc = c["location"] or c["surface_condition"] or "unknown location"
                lines.append(f"  • {loc}: {c['traction']}")
        else:
            lines.append("\nNo chain laws or traction advisories.")
    else:
        lines.append("Road condition data unavailable — check cotrip.org directly.")

    return "\n".join(lines)
