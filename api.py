"""
Colorado Powracle — FastAPI chat endpoint.
Run: uvicorn api:app --reload
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent.agent import build_agent
from agent.chat_service import run_chat_turn
from agent.deterministic_answers import try_answer_simple_live_question
from ingestion.openmeteo_forecast import get_weekend_snowfall
from ingestion.snotel_live import fetch_all_snowpack
from resorts import RESORT_STATIONS, STARTING_CITIES, pass_filter


app = FastAPI(title="Colorado Powracle API")


# ── Pydantic models ──────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    messages: list[Message] = Field(default_factory=list)
    selected_passes: list[str] = Field(default_factory=lambda: ["All"])
    start_city: str = "Denver"
    use_deterministic_simple_answers: bool = False


class ChatResponse(BaseModel):
    answer: str
    ranking: list[str]
    raw_response: str


# ── Lazy agent init (avoids crash on import if API key is missing) ───────────

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent(verbose=True)
    return _agent


# ── Cached data loaders (TTL-based, no Streamlit dependency) ─────────────────

_conditions_cache: dict = {"data": None, "expires": 0}
_forecasts_cache: dict = {"data": None, "expires": 0}

_CONDITIONS_TTL = 1800   # 30 min, same as app.py
_FORECASTS_TTL = 10800   # 3 hr, same as app.py


def _load_conditions() -> dict[str, Any]:
    now = time.time()
    if _conditions_cache["data"] is not None and now < _conditions_cache["expires"]:
        return _conditions_cache["data"]

    station_to_resorts: dict[str, list[str]] = {}
    for resort, info in RESORT_STATIONS.items():
        sid = info.get("station_id")
        if sid:
            station_to_resorts.setdefault(sid, []).append(resort)

    batch = fetch_all_snowpack(list(station_to_resorts.keys()))
    out = {resort: None for resort in RESORT_STATIONS}
    for triplet, data in batch.items():
        for resort in station_to_resorts.get(triplet, []):
            out[resort] = data

    _conditions_cache["data"] = out
    _conditions_cache["expires"] = now + _CONDITIONS_TTL
    return out


def _load_forecasts() -> dict[str, Any]:
    now = time.time()
    if _forecasts_cache["data"] is not None and now < _forecasts_cache["expires"]:
        return _forecasts_cache["data"]

    def _fetch(resort: str, info: dict[str, Any]):
        if not info.get("lat"):
            return resort, None
        try:
            return resort, get_weekend_snowfall(info["lat"], info["lon"])
        except Exception:
            return resort, None

    out = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch, r, i): r for r, i in RESORT_STATIONS.items()}
        for f in as_completed(futures):
            resort, data = f.result()
            out[resort] = data

    _forecasts_cache["data"] = out
    _forecasts_cache["expires"] = now + _FORECASTS_TTL
    return out


# ── Helpers ──────────────────────────────────────────────────────────────────

def _allowed_resorts(selected_passes: list[str]) -> list[str]:
    return [r for r in RESORT_STATIONS if pass_filter(r, selected_passes)]


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def _build_agent_prompt(question: str, selected_passes: list[str], start_city: str) -> str:
    conditions = _load_conditions()
    forecasts = _load_forecasts()

    cond_snapshot = "\n".join(
        f'  - {r}: {conditions[r].get("new_snow_72h", 0):.1f}" new (72h), '
        f'{conditions[r].get("new_snow_48h", 0):.1f}" new (48h), '
        f'{conditions[r].get("new_snow_24h", 0):.1f}" new (24h), '
        f'{conditions[r].get("snow_depth_in", 0):.1f}" base'
        if conditions.get(r) else f"  - {r}: no live data"
        for r in RESORT_STATIONS
    )

    forecast_snapshot = "\n".join(
        f'  - {r}: Sat {forecasts[r]["saturday_snow_in"]:.1f}" / '
        f'Sun {forecasts[r]["sunday_snow_in"]:.1f}" / '
        f'weekend total {forecasts[r]["weekend_total_in"]:.1f}"'
        if forecasts.get(r) else f"  - {r}: no forecast"
        for r in RESORT_STATIONS
    )

    context = (
        f"[Live snowpack for all resorts right now:\n{cond_snapshot}]\n\n"
        f"[Weekend snowfall forecast (Open-Meteo):\n{forecast_snapshot}]\n\n"
    )

    if start_city in STARTING_CITIES:
        user_lat, user_lon = STARTING_CITIES[start_city]
        distance_snapshot = "\n".join(
            f"  - {r}: {_haversine_miles(user_lat, user_lon, RESORT_STATIONS[r]['lat'], RESORT_STATIONS[r]['lon']):.0f} mi from {start_city}"
            for r in RESORT_STATIONS
            if RESORT_STATIONS[r].get("lat") is not None and RESORT_STATIONS[r].get("lon") is not None
        )
        context += (
            f"[User context: starting city is {start_city}.\n"
            f"Distances from {start_city}:\n{distance_snapshot}]\n\n"
        )
    else:
        context += f"[User context: starting city is {start_city}.]\n\n"

    if selected_passes and "All" not in selected_passes:
        pass_str = " and ".join(selected_passes)
        pass_resorts = _allowed_resorts(selected_passes)
        return (
            context
            + f"[User context: I have a {pass_str} Pass. "
            + f"Only recommend resorts on my pass: {', '.join(pass_resorts)}.]\n\n"
            + question
        )

    return context + question


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    allowed_resorts = _allowed_resorts(request.selected_passes)

    if request.use_deterministic_simple_answers:
        conditions = _load_conditions()
        simple_result = try_answer_simple_live_question(
            question=request.question,
            conditions=conditions,
            selected_passes=request.selected_passes,
            resort_stations=RESORT_STATIONS,
            pass_filter_fn=pass_filter,
        )
        if simple_result is not None:
            filtered_ranking = [r for r in simple_result["ranking"] if r in allowed_resorts]
            return ChatResponse(
                answer=simple_result["answer"],
                ranking=filtered_ranking,
                raw_response=simple_result["answer"],
            )

    agent_prompt = _build_agent_prompt(
        question=request.question,
        selected_passes=request.selected_passes,
        start_city=request.start_city,
    )

    messages = [m.model_dump() for m in request.messages]
    messages.append({"role": "user", "content": request.question})

    chat_result = run_chat_turn(
        agent=_get_agent(),
        messages=messages,
        agent_prompt=agent_prompt,
        resort_names=allowed_resorts,
    )

    filtered_ranking = [r for r in chat_result["ranking"] if r in allowed_resorts]

    return ChatResponse(
        answer=chat_result["response_display"],
        ranking=filtered_ranking,
        raw_response=chat_result["raw_response"],
    )
