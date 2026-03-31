from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent.agent import build_agent
from agent.chat_service import run_chat_turn
from agent.deterministic_answers import try_answer_simple_live_question
from ingestion.openmeteo_forecast import get_weekend_snowfall
from ingestion.snotel_live import fetch_all_snowpack
from resorts import RESORT_STATIONS, pass_filter


app = FastAPI(title="Colorado Powracle API")


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


_STARTING_CITIES = {
    "Denver": (39.7392, -104.9903),
    "Boulder": (40.0150, -105.2705),
    "Colorado Springs": (38.8339, -104.8214),
    "Fort Collins": (40.5853, -105.0844),
    "Pueblo": (38.2544, -104.6091),
    "Grand Junction": (39.0639, -108.5506),
}


def _resort_passes(resort: str) -> list[str]:
    return RESORT_STATIONS[resort].get("pass", [])


def _pass_filter(resort: str, selected: list[str]) -> bool:
    if not selected or "All" in selected:
        return True
    return any(p in _resort_passes(resort) for p in selected)


def _load_conditions() -> dict[str, Any]:
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
    return out


def _load_forecasts() -> dict[str, Any]:
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
    return out


AGENT = build_agent(verbose=True)


def _build_agent_prompt(question: str, selected_passes: list[str]) -> str:
    conditions = _load_conditions()
    forecasts = _load_forecasts()

    cond_snapshot = "\n".join(
        f"  - {r}: {conditions[r].get('new_snow_72h', 0):.1f}\" new (72h), "
        f"{conditions[r].get('new_snow_48h', 0):.1f}\" new (48h), "
        f"{conditions[r].get('new_snow_24h', 0):.1f}\" new (24h), "
        f"{conditions[r].get('snow_depth_in', 0):.1f}\" base"
        if conditions.get(r) else f"  - {r}: no live data"
        for r in RESORT_STATIONS
    )

    forecast_snapshot = "\n".join(
        f"  - {r}: Sat {forecasts[r]['saturday_snow_in']:.1f}\" / "
        f"Sun {forecasts[r]['sunday_snow_in']:.1f}\" / "
        f"weekend total {forecasts[r]['weekend_total_in']:.1f}\""
        if forecasts.get(r) else f"  - {r}: no forecast"
        for r in RESORT_STATIONS
    )

    context = (
        f"[Live snowpack for all resorts right now:\n{cond_snapshot}]\n\n"
        f"[Weekend snowfall forecast (Open-Meteo):\n{forecast_snapshot}]\n\n"
    )

    if selected_passes and "All" not in selected_passes:
        pass_str = " and ".join(selected_passes)
        pass_resorts = [r for r in RESORT_STATIONS if _pass_filter(r, selected_passes)]
        return (
            context
            + f"[User context: I have a {pass_str} Pass. "
            + f"Only recommend resorts on my pass: {', '.join(pass_resorts)}.]\n\n"
            + question
        )

    return context + question


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
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
            return ChatResponse(
                answer=simple_result["answer"],
                ranking=simple_result["ranking"],
                raw_response=simple_result["answer"],
            )

    agent_prompt = _build_agent_prompt(
        question=request.question,
        selected_passes=request.selected_passes,
    )

    messages = [m.model_dump() for m in request.messages]
    messages.append({"role": "user", "content": request.question})

    chat_result = run_chat_turn(
        agent=AGENT,
        messages=messages,
        agent_prompt=agent_prompt,
        resort_names=list(RESORT_STATIONS.keys()),
    )

    return ChatResponse(
        answer=chat_result["response_display"],
        ranking=chat_result["ranking"],
        raw_response=chat_result["raw_response"],
    )
