# Colorado Powder Oracle — Architecture

## Simple Overview

```mermaid
graph LR
    User(["🎿 User"]) --> UI["Streamlit UI<br/>app.py"]

    UI -->|cached snapshots| APIs
    UI -->|chat question| Agent["ReAct Agent<br/>Claude 3 Haiku"]

    Agent -->|Thought → Action → Observe| Tools["6 LangChain Tools"]

    Tools --> APIs["External APIs<br/>SNOTEL · COtrip · Open-Meteo · SerpAPI"]
    Tools --> DB["DuckDB<br/>10yr snow + traffic history"]

    Agent -->|answer| UI
```

---

## Detailed Architecture

```mermaid
graph TB
    %% ── User Layer ──────────────────────────────────────────────────
    User(["🎿 User"])
    User -->|question| UI

    subgraph UI ["Streamlit App (app.py)"]
        direction TB
        Chat["💬 Chat Interface<br/>st.chat_input / st.chat_message"]
        Cards["❄️ Resort Condition Cards<br/>19 resorts, sorted by snow/distance/AI pick"]
        Map["🗺️ Plotly Scattermap<br/>ESRI World Topo tiles, pass-colored markers"]
        Filters["🎛️ Controls<br/>Pass filter (IKON/EPIC/INDY) · Starting city · Sort"]
    end

    %% ── Agent Layer ─────────────────────────────────────────────────
    UI -->|agent_prompt + live snapshot + chat history| Agent

    subgraph Agent ["LangChain ReAct Agent (agent/)"]
        direction TB
        LLM["Claude 3 Haiku<br/>via OpenRouter"]
        Prompt["System Prompt<br/>resort knowledge · traffic rules · tool guidance"]
        Loop["ReAct Loop<br/>Thought → Action → Observation → repeat"]
        LLM --- Prompt
        LLM --- Loop
    end

    %% ── Tool Layer ──────────────────────────────────────────────────
    Agent -->|selects tool based on reasoning| Tools

    subgraph Tools ["LangChain Tools (tools/)"]
        direction TB
        T1["get_current_snowpack<br/>snowpack_tools.py"]
        T2["get_snowpack_history<br/>snowpack_tools.py"]
        T3["get_live_traffic<br/>traffic_tools.py"]
        T4["get_best_departure_time<br/>traffic_tools.py"]
        T5["get_snow_forecast<br/>forecast_tools.py"]
        T6["web_search<br/>search_tools.py"]
    end

    %% ── Data Layer ──────────────────────────────────────────────────
    subgraph External ["External APIs"]
        direction TB
        SNOTEL_API["SNOTEL REST API<br/>wcc.sc.egov.usda.gov<br/>(no key)"]
        COTRIP_API["COtrip API<br/>data.cotrip.org<br/>(COTRIP_API_KEY)"]
        OPENMETEO["Open-Meteo API<br/>HRRR → best_match fallback<br/>(no key)"]
        SERP["SerpAPI<br/>(SERPAPI_API_KEY)"]
    end

    subgraph DB ["DuckDB (powder_oracle.duckdb)"]
        direction TB
        Snowpack["snowpack table<br/>40K+ rows · 10yr daily readings"]
        Traffic["traffic_history table<br/>850K rows · hourly sensor counts"]
        V1["monthly_averages view"]
        V2["season_summary view"]
        V3["traffic_patterns view"]
        Snowpack --> V1
        Snowpack --> V2
        Traffic --> V3
    end

    subgraph Ingestion ["Data Ingestion (ingestion/)"]
        direction TB
        SH["snotel_historical.py<br/>bulk CSV download"]
        SL["snotel_live.py<br/>fetch_current_snowpack()"]
        CH["cdot_historical.py<br/>synthetic traffic generator"]
        CL["cotrip_live.py<br/>fetch_incidents() · fetch_road_conditions()"]
        OF["openmeteo_forecast.py<br/>fetch_snow_forecast()"]
    end

    subgraph Static ["Static Config"]
        Resorts["resorts.py<br/>19 resorts · SNOTEL station IDs<br/>coordinates · corridors · pass tags"]
    end

    %% ── Tool → Data connections ─────────────────────────────────────
    T1 --> SL
    SL --> SNOTEL_API

    T2 --> DB

    T3 --> CL
    CL --> COTRIP_API
    T3 -.->|fallback when no API key| T6

    T4 --> DB

    T5 --> OF
    OF --> OPENMETEO

    T6 --> SERP

    %% ── Ingestion → Storage ─────────────────────────────────────────
    SH -->|CSV → Parquet| DB
    CH -->|CSV → Parquet| DB

    %% ── UI direct data fetches (cached, not through agent) ──────────
    UI -->|batch fetch, cached 30min| SL
    UI -->|weekend forecast, cached 3hr| OF
    UI --> Resorts

    %% ── Shared config ───────────────────────────────────────────────
    T1 --> Resorts
    T2 --> Resorts
    T5 --> Resorts

    %% ── Styling ─────────────────────────────────────────────────────
    classDef api fill:#1a3a5c,stroke:#4a9eed,color:#e0f0ff
    classDef db fill:#1a3a2c,stroke:#4aed7a,color:#e0ffe8
    classDef tool fill:#3a1a5c,stroke:#9a4aed,color:#f0e0ff
    classDef ui fill:#5c3a1a,stroke:#ed9a4a,color:#fff0e0
    classDef agent fill:#5c1a2a,stroke:#ed4a6a,color:#ffe0e8

    class SNOTEL_API,COTRIP_API,OPENMETEO,SERP api
    class Snowpack,Traffic,V1,V2,V3 db
    class T1,T2,T3,T4,T5,T6 tool
    class Chat,Cards,Map,Filters ui
    class LLM,Prompt,Loop agent
```

## Data Flow Summary

| Path | Flow | Latency |
|------|------|---------|
| **Live snow** | User → UI (cached) → `snotel_live.py` → SNOTEL API | ~2s (batch, cached 30min) |
| **Historical snow** | User → Agent → `get_snowpack_history` → DuckDB | ~50ms |
| **Live traffic** | User → Agent → `get_live_traffic` → COtrip API | ~1s |
| **Historical traffic** | User → Agent → `get_best_departure_time` → DuckDB | ~50ms |
| **Forecast** | User → UI (cached) → `openmeteo_forecast.py` → Open-Meteo API | ~1s (cached 3hr) |
| **Web search** | User → Agent → `web_search` → SerpAPI | ~2s |

## Key Design Decisions

1. **DuckDB over traditional DB** — Columnar storage matches our analytical workload (aggregations across many rows, few columns). No server infrastructure needed.
2. **ReAct agent** — LLM reasons step-by-step, selecting tools based on the question. Handles multi-part questions (snow + traffic) in a single conversation turn.
3. **Dual data paths** — UI fetches live conditions directly (cached, fast page load). Agent queries the same APIs on-demand for conversational questions.
4. **Graceful degradation** — Every tool returns an actionable message on failure, never raises exceptions. Missing API keys trigger fallback to `web_search`.
