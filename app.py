"""
Colorado Powracle — Streamlit web app.
Run: streamlit run app.py  (from project root, with conda env active)
"""

from concurrent.futures import ThreadPoolExecutor as _TPE
from agent.agent import build_agent
from ingestion.snotel_live import fetch_current_snowpack, fetch_all_snowpack
from ingestion.openmeteo_forecast import get_weekend_snowfall
from resorts import RESORT_STATIONS
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
import sys
import os
import math
import re
import ast

# Ensure project root is on sys.path so package imports work when running via streamlit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


st.set_page_config(
    page_title="Colorado Powracle",
    page_icon="⛷️",
    layout="wide"
)

st.markdown("""
<style>
/* ── Snowfall effect ──────────────────────────────────────────────── */
/* Hide the markdown container holding the snowfall effect */
div[data-testid="stMarkdownContainer"]:has(#snowfall-container) {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
    z-index: 999999 !important;
}

#snowfall-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
    z-index: 999999;
    overflow: hidden;
}
.snowflake {
    position: fixed;
    top: -10px;
    color: rgba(255, 255, 255, 0.85);
    text-shadow: 0 0 3px rgba(255, 255, 255, 0.5);
    font-size: 1em;
    pointer-events: none;
    animation: fall linear infinite;
    user-select: none;
}
@keyframes fall {
    0% {
        transform: translateY(-10px) rotate(0deg);
    }
    100% {
        transform: translateY(100vh) rotate(360deg);
    }
}

/* ── Unified text hierarchy ───────────────────────────────────────── */
/* L3 — Content text: widget labels, dropdowns, radio, captions, chat */
[data-testid="stWidgetLabel"] p,
label,
[data-testid="stSelectbox"] div[data-baseweb="select"] span,
[data-testid="stMultiSelect"] span,
.stRadio label span,
[data-testid="stCaptionContainer"] p,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatInput"] textarea {
    font-size: 0.97rem !important;
    line-height: 1.6 !important;
}

/* ── Expanders (map & trip planner) ──────────────────────────────── */
[data-testid="stExpander"] {
    border: 1.5px solid rgba(99, 179, 237, 0.2) !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2) !important;
    overflow: hidden !important;
}
/* Trip planner specific styling */
[data-testid="stExpander"]:has(button[aria-label*="Trip"]) {
    background: linear-gradient(135deg, rgba(52,211,153,0.03), rgba(41,182,246,0.03));
    border-color: rgba(52,211,153,0.25) !important;
}

/* ── Plotly chart rounding ────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    border-radius: 14px !important;
    overflow: hidden !important;
}
[data-testid="stPlotlyChart"] > div,
[data-testid="stPlotlyChart"] iframe {
    border-radius: 14px !important;
    overflow: hidden !important;
}

/* ── Chat messages ────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    border-radius: 14px !important;
    border-width: 1px !important;
    border-style: solid !important;
    border-color: rgba(99, 179, 237, 0.12) !important;
}

/* ── Resort cards ─────────────────────────────────────────────────── */
.resort-card {
    padding: 9px 13px;
    margin-bottom: 5px;
    border-radius: 11px;
    border: 1px solid rgba(99, 179, 237, 0.1);
    background: rgba(255, 255, 255, 0.04);
    transition: border-color 0.18s, background 0.18s;
    line-height: 1.5;
}
.resort-card:hover {
    border-color: rgba(99, 179, 237, 0.28);
    background: rgba(255, 255, 255, 0.07);
}
.resort-card-top {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
}
.resort-dot { font-size: 1.1em; vertical-align: middle; line-height: 1; }
.resort-name { font-weight: 600; font-size: 0.97rem; }
.resort-dist { font-size: 0.88rem; opacity: 0.55; margin-left: auto; white-space: nowrap; }
.resort-stats { font-size: 0.97rem; opacity: 0.72; margin-top: 1px; padding-left: 20px; }
.resort-no-data { font-size: 0.88rem; opacity: 0.5; margin-top: 1px; padding-left: 20px; }
</style>
""", unsafe_allow_html=True)

# ── Agent + chat history (once per session) ───────────────────────────────────

if "agent" not in st.session_state:
    st.session_state.agent = build_agent(verbose=True)
    st.session_state.messages = []

# ── Cache functions (defined here, called after page skeleton renders) ─────────


@st.cache_data(ttl=1800)
def load_conditions():
    """Single batch SNOTEL call for all stations — ~10x faster than per-resort calls."""
    # Multiple resorts can share a station; map triplet → list of resorts
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


@st.cache_data(ttl=10800)
def load_forecasts():
    """Weekend snowfall forecast for all resorts — parallel Open-Meteo calls."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch(resort, info):
        if not info.get("lat"):
            return resort, None
        try:
            return resort, get_weekend_snowfall(info["lat"], info["lon"])
        except Exception:
            return resort, None

    out = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch, r, i): r for r,
                   i in RESORT_STATIONS.items()}
        for f in as_completed(futures):
            resort, data = f.result()
            out[resort] = data
    return out


@st.cache_data(ttl=10800)
def load_7day_forecasts():
    """Full 7-day forecast for all resorts — parallel Open-Meteo calls."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ingestion.openmeteo_forecast import fetch_snow_forecast

    def _fetch(resort, info):
        if not info.get("lat"):
            return resort, None
        try:
            return resort, fetch_snow_forecast(info["lat"], info["lon"], days=7)
        except Exception:
            return resort, None

    out = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch, r, i): r for r,
                   i in RESORT_STATIONS.items()}
        for f in as_completed(futures):
            resort, data = f.result()
            out[resort] = data
    return out


# ── Pass filter helpers ────────────────────────────────────────────────────────

_ALL_PASSES = ["IKON", "EPIC", "INDY"]


def _resort_passes(resort: str) -> list[str]:
    return RESORT_STATIONS[resort].get("pass", [])


def _pass_filter(resort: str, selected: list[str]) -> bool:
    """True if resort should be shown given the selected pass list."""
    if not selected or "All" in selected:
        return True
    return any(p in _resort_passes(resort) for p in selected)


# ── Location + visual constants ───────────────────────────────────────────────

_STARTING_CITIES = {
    "Denver":           (39.7392, -104.9903),
    "Boulder":          (40.0150, -105.2705),
    "Colorado Springs": (38.8339, -104.8214),
    "Fort Collins":     (40.5853, -105.0844),
    "Pueblo":           (38.2544, -104.6091),
    "Grand Junction":   (39.0639, -108.5506),
}


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line great-circle distance in miles."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


# Map marker style per pass
_PASS_STYLE = {
    "IKON": {"symbol": "circle", "border": "#29B6F6"},
    "EPIC": {"symbol": "circle", "border": "#CE93D8"},
    "INDY": {"symbol": "circle", "border": "#66BB6A"},
}

# Colored HTML pill per pass (used in condition cards)
_PASS_BADGE = {
    "IKON": '<span style="background:rgba(41,182,246,0.18);color:#7dd3fc;padding:2px 7px;border-radius:20px;font-size:0.7em;font-weight:700;letter-spacing:0.07em;border:1px solid rgba(41,182,246,0.3)">IKON</span>',
    "EPIC": '<span style="background:rgba(167,139,250,0.18);color:#c4b5fd;padding:2px 7px;border-radius:20px;font-size:0.7em;font-weight:700;letter-spacing:0.07em;border:1px solid rgba(167,139,250,0.3)">EPIC</span>',
    "INDY": '<span style="background:rgba(52,211,153,0.18);color:#6ee7b7;padding:2px 7px;border-radius:20px;font-size:0.7em;font-weight:700;letter-spacing:0.07em;border:1px solid rgba(52,211,153,0.3)">INDY</span>',
}


def _blues_color(t: float) -> str:
    """Map t ∈ [0, 1] to a soft blue hex color visible on a light background."""
    stops = [
        (0.000, (200, 225, 248)),
        (0.125, (160, 203, 238)),
        (0.250, (110, 174, 222)),
        (0.375, (70, 144, 205)),
        (0.500, (40, 112, 185)),
        (0.625, (20,  82, 158)),
        (0.750, (10,  57, 130)),
        (0.875, (5,  37,  99)),
        (1.000, (2,  20,  70)),
    ]
    t = max(0.0, min(1.0, t))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#021446"


# Matching colorscale for Plotly map markers (same stops as _blues_color)
_SNOW_CS = [
    [0.000, "rgb(200,225,248)"],
    [0.125, "rgb(160,203,238)"],
    [0.250, "rgb(110,174,222)"],
    [0.375, "rgb(70,144,205)"],
    [0.500, "rgb(40,112,185)"],
    [0.625, "rgb(20,82,158)"],
    [0.750, "rgb(10,57,130)"],
    [0.875, "rgb(5,37,99)"],
    [1.000, "rgb(2,20,70)"],
]


# ── Seed session state so widgets work on first load ──────────────────────────

if "pass_filter" not in st.session_state:
    st.session_state.pass_filter = ["All"]
if "start_city" not in st.session_state:
    st.session_state.start_city = "Denver"
if "sort_by" not in st.session_state:
    st.session_state.sort_by = "🌨️ Fresh Snow"
if "snowfall_enabled" not in st.session_state:
    st.session_state.snowfall_enabled = False

# ── First-load detection ───────────────────────────────────────────────────────
# On first load, conditions are not yet fetched. We render the layout (including
# the chat column) immediately so the user can start typing, then load data in
# the background and fill the cards placeholder before calling st.rerun() to
# show the map. On every subsequent rerun, data comes instantly from session state.

_first_load = "conditions" not in st.session_state

# ── Widget values from session state (used by map, which renders before widgets) ─

selected_passes = st.session_state.pass_filter or ["All"]
city_name       = st.session_state.start_city
sort_by         = st.session_state.sort_by
user_lat, user_lon = _STARTING_CITIES[city_name]

# ── Pre-compute display values (only when data is available) ──────────────────

if not _first_load:
    conditions    = st.session_state.conditions
    forecasts     = st.session_state.forecasts
    visible       = {r: d for r, d in conditions.items() if _pass_filter(r, selected_passes)}
    vis_names     = list(visible.keys())
    _use_base_map = sort_by == "🏔️ Base Snow"
    _map_field    = "snow_depth_in" if _use_base_map else "new_snow_72h"
    _map_label    = "Base depth (in)" if _use_base_map else "72h snow (in)"
    _map_floor    = 30 if _use_base_map else 6
    _map_scale    = 0.2 if _use_base_map else 2
    _all_map_vals = [visible[r].get(_map_field, 0) if visible[r] else 0 for r in vis_names]
    _CMIN         = 0
    _CMAX         = max(max(_all_map_vals, default=0), _map_floor)

# ── Map (full-width, inline — only once data is loaded) ───────────────────────

if not _first_load:
    with st.expander("🗺️ Show Resort Map", expanded=False):
            fig = go.Figure()

            # Precompute per-pass data once, reused across both render loops
            _pass_data = {}
            for pass_name, style in _PASS_STYLE.items():
                p_resorts = [r for r in vis_names
                             if pass_name in RESORT_STATIONS[r].get("pass", [])]
                if not p_resorts:
                    continue
                p_snows = [visible[r].get("new_snow_72h", 0)
                           if visible[r] else 0 for r in p_resorts]
                p_bases = [visible[r].get("snow_depth_in", 0)
                           if visible[r] else 0 for r in p_resorts]
                p_map_vals = [p_bases[i] if _use_base_map else p_snows[i]
                              for i in range(len(p_resorts))]
                p_dists = [_haversine_miles(user_lat, user_lon,
                                            RESORT_STATIONS[r]["lat"], RESORT_STATIONS[r]["lon"])
                           for r in p_resorts]
                p_texts = [
                    (f"<b>{r}</b>  [{pass_name}]<br>"
                     f"❄ New 72h: {p_snows[i]:.0f}\"  ·  Base: {p_bases[i]:.0f}\"<br>"
                     f"📍 {p_dists[i]:.0f} mi from {city_name}")
                    for i, r in enumerate(p_resorts)
                ]
                p_sizes = [max(10, min(36, v * _map_scale + 10))
                           for v in p_map_vals]
                _pass_data[pass_name] = dict(
                    resorts=p_resorts, map_vals=p_map_vals,
                    texts=p_texts, sizes=p_sizes, style=style,
                )

            # Layer 1 — pass-colored halos (rendered first, sit underneath)
            for pass_name, d in _pass_data.items():
                fig.add_trace(go.Scattermap(
                    lat=[RESORT_STATIONS[r]["lat"] for r in d["resorts"]],
                    lon=[RESORT_STATIONS[r]["lon"] for r in d["resorts"]],
                    mode="markers",
                    name=pass_name,
                    hoverinfo="skip",
                    marker=dict(
                        size=[min(s + 12, 48) for s in d["sizes"]],
                        color=d["style"]["border"],
                        opacity=0.55,
                    ),
                ))

            # Layer 2 — snow-level colorscale fill (rendered on top, carries hover + colorbar)
            first_colorbar = True
            for pass_name, d in _pass_data.items():
                colorbar_cfg = dict(
                    title=dict(text=_map_label, font=dict(
                        color="#0d1b2e", size=11)),
                    thickness=12, len=0.55,
                    tickfont=dict(color="#0d1b2e", size=10),
                    bgcolor="rgba(220,238,255,0.92)",
                    bordercolor="#90b8d8",
                    borderwidth=1,
                ) if first_colorbar else None
                fig.add_trace(go.Scattermap(
                    lat=[RESORT_STATIONS[r]["lat"] for r in d["resorts"]],
                    lon=[RESORT_STATIONS[r]["lon"] for r in d["resorts"]],
                    text=d["texts"],
                    hoverinfo="text",
                    mode="markers",
                    showlegend=False,
                    marker=dict(
                        size=d["sizes"],
                        color=d["map_vals"],
                        colorscale=_SNOW_CS,
                        cmin=_CMIN, cmax=_CMAX,
                        showscale=first_colorbar,
                        colorbar=colorbar_cfg,
                        opacity=0.95,
                    ),
                ))
                first_colorbar = False

            fig.add_trace(go.Scattermap(
                lat=[user_lat], lon=[user_lon],
                mode="markers+text",
                text=[f"  {city_name}"],
                textposition="bottom right",
                textfont=dict(color="#b83200", size=12, family="Arial Black"),
                hovertext=f"📍 {city_name}",
                hoverinfo="text",
                marker=dict(size=18, color="#e03c00"),
                name="📍 You",
                showlegend=True,
            ))

            fig.update_layout(
                map=dict(
                    style="white-bg",
                    layers=[{
                        "below": "traces",
                        "sourcetype": "raster",
                        "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"],
                        "sourceattribution": "© Esri / World Topo Map",
                    }],
                    center=dict(lat=39.0, lon=-105.55),
                    zoom=6.5,
                ),
                margin={"r": 0, "t": 0, "l": 0, "b": 0},
                height=520,
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(
                    x=0.01, y=0.99,
                    bgcolor="rgba(220,238,255,0.92)",
                    bordercolor="#90b8d8",
                    borderwidth=1,
                    font=dict(color="#0d1b2e", size=11),
                    itemsizing="constant",
                ),
            )
            st.plotly_chart(fig, width="stretch")

# ── Two-column layout: conditions | chat ─────────────────────────────────────

col_left, col_right = st.columns([1, 1.5], gap="large")

# ── LEFT: controls + live condition cards ────────────────────────────────────

with col_left:
    # Title with snowfall toggle (isolated fragment to prevent full page rerun)
    @st.fragment
    def snowfall_toggle():
        title_col, toggle_col = st.columns([4, 1])
        with title_col:
            st.markdown("### ⛷️ Colorado Powracle")
        with toggle_col:
            st.checkbox(
                "❄️",
                value=st.session_state.snowfall_enabled,
                key="snowfall_enabled",
                help="Toggle snowfall effect"
            )

        # Render snowfall effect inside fragment so it updates on toggle
        if st.session_state.snowfall_enabled:
            import random
            random.seed(42)  # Consistent positions across reruns

            snowflakes_html = '<div id="snowfall-container">'
            for i in range(50):
                left = random.randint(0, 100)
                size = random.uniform(0.5, 1.5)
                opacity = random.uniform(0.3, 0.9)
                duration = random.uniform(10, 25)
                delay = random.uniform(0, 10)

                snowflakes_html += f'<div class="snowflake" style="left:{left}%;font-size:{size}em;opacity:{opacity};animation-duration:{duration}s;animation-delay:{delay}s;">❄</div>'
            snowflakes_html += '</div>'

            st.markdown(snowflakes_html, unsafe_allow_html=True)

    snowfall_toggle()

    selected_passes = st.multiselect(
        "My pass(es):",
        options=["All"] + _ALL_PASSES,
        key="pass_filter",
        help="Filter resorts to only those included on your ski pass(es).",
    )
    if not selected_passes:
        selected_passes = ["All"]

    city_name = st.selectbox(
        "Starting from:",
        options=list(_STARTING_CITIES.keys()),
        key="start_city",
    )
    user_lat, user_lon = _STARTING_CITIES[city_name]

    sort_by = st.radio(
        "Sort by:",
        options=["🌨️ Fresh Snow", "🏔️ Base Snow", "📍 Distance", "🤖 AI Pick"],
        horizontal=True,
        key="sort_by",
    )

    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin:6px 0 4px 0;">'
        '<span style="font-size:1.15rem;font-weight:700;letter-spacing:-0.01em;">❄️ Live Conditions</span>'
        '<div style="flex:1;height:1.5px;background:linear-gradient(to right,rgba(99,179,237,0.35),transparent);margin-left:4px;"></div>'
        '</div>',
        unsafe_allow_html=True)

    if _first_load:
        # Placeholder shown while data loads in the background
        _cards_ph = st.empty()
        _cards_ph.markdown(
            '<div style="padding:14px 4px;opacity:0.6;font-size:0.9rem;">⏳ Loading snow conditions…</div>',
            unsafe_allow_html=True)
    else:
        # Recalculate visible with current widget values (user may have changed filter)
        visible = {r: d for r, d in conditions.items() if _pass_filter(r, selected_passes)}

        _use_base_map = sort_by == "🏔️ Base Snow"
        _map_scale    = 0.2 if _use_base_map else 2
        _map_floor    = 30 if _use_base_map else 6
        _all_map_vals = [visible[r].get("snow_depth_in" if _use_base_map else "new_snow_72h", 0)
                         if visible[r] else 0 for r in visible]
        _CMAX         = max(max(_all_map_vals, default=0), _map_floor)

        if sort_by == "🤖 AI Pick":
            if "ai_pick_ranking" in st.session_state:
                _rank_map = {r: i for i, r in enumerate(st.session_state["ai_pick_ranking"])}
                _ordered = sorted(visible.items(), key=lambda x: _rank_map.get(x[0], 999))
            else:
                _ordered = sorted(
                    visible.items(),
                    key=lambda x: -(x[1].get("new_snow_72h", 0) if x[1] else 0)
                )
                st.caption("💬 Ask a question to personalise the AI Pick ranking.")
        else:
            def _sort_key(item):
                resort, d = item
                if sort_by == "📍 Distance":
                    return _haversine_miles(
                        user_lat, user_lon,
                        RESORT_STATIONS[resort]["lat"], RESORT_STATIONS[resort]["lon"]
                    )
                elif sort_by == "🏔️ Base Snow":
                    return -(d.get("snow_depth_in", 0) if d else 0)
                else:
                    return -(d.get("new_snow_72h", 0) if d else 0)
            _ordered = sorted(visible.items(), key=_sort_key)

        cards_html = []
        for resort, d in _ordered:
            badges = " ".join(_PASS_BADGE[p] for p in _resort_passes(resort))
            dist = _haversine_miles(
                user_lat, user_lon,
                RESORT_STATIONS[resort]["lat"], RESORT_STATIONS[resort]["lon"]
            )
            if d is None:
                cards_html.append(
                    f'<div class="resort-card">'
                    f'<div class="resort-card-top">'
                    f'<span class="resort-dot" style="color:#5a8fb5">○</span>'
                    f'<span class="resort-name">{resort}</span>{badges}'
                    f'<span class="resort-dist">{dist:.0f} mi</span>'
                    f'</div>'
                    f'<div class="resort-no-data">no SNOTEL — check resort site</div>'
                    f'</div>'
                )
                continue
            new72 = d.get("new_snow_72h", 0)
            base = d.get("snow_depth_in", 0)
            _val = base if _use_base_map else new72
            _t = (_val / _CMAX) if _CMAX > 0 else 0
            dot_color = _blues_color(_t)
            cards_html.append(
                f'<div class="resort-card">'
                f'<div class="resort-card-top">'
                f'<span class="resort-dot" style="color:{dot_color}">●</span>'
                f'<span class="resort-name">{resort}</span>{badges}'
                f'<span class="resort-dist">{dist:.0f} mi</span>'
                f'</div>'
                f'<div class="resort-stats">{new72:.0f}" new (72h) · {base:.0f}" base</div>'
                f'</div>'
            )
        st.markdown("".join(cards_html), unsafe_allow_html=True)

# ── RIGHT: chat ───────────────────────────────────────────────────────────────

with col_right:
    st.markdown("### 💬 Ask the Powracle")
    st.caption(
        "Ask me where to ski, which resort has the best snow, "
        "or how this season compares to average.")

    # ── Smart Trip Planner ────────────────────────────────────────────────
    with st.expander("🗓️ Smart Trip Planner", expanded=False):
        st.markdown("Plan a multi-day ski trip with optimal resort recommendations, forecast analysis, and traffic timing.")

        plan_col1, plan_col2 = st.columns(2)
        with plan_col1:
            from datetime import datetime, timedelta
            trip_start = st.date_input(
                "Start date:",
                value=datetime.now() + timedelta(days=3),
                min_value=datetime.now().date(),
                max_value=datetime.now().date() + timedelta(days=14),
                help="When does your trip start?"
            )
        with plan_col2:
            num_days = st.slider(
                "Number of days:",
                min_value=1,
                max_value=7,
                value=3,
                help="How many days will you ski?"
            )

        lodging_pref = st.selectbox(
            "Lodging preference (optional):",
            options=["Flexible", "I-70 Corridor (Vail, Breck, etc.)", "Summit County", "Steamboat", "Aspen/Snowmass", "Wolf Creek area"],
            help="Where do you prefer to stay? This helps optimize driving."
        )

        trip_notes = st.text_area(
            "Additional preferences:",
            placeholder="e.g., 'Avoid I-70 on weekends', 'Prefer tree skiing', 'Looking for steeps'",
            height=60
        )

        if st.button("🎿 Generate Trip Plan", type="primary", use_container_width=True):
            if not _first_load:
                # Build trip planning prompt
                trip_prompt = f"""I'm planning a {num_days}-day ski trip starting {trip_start.strftime('%A, %B %d')}.

REQUIREMENTS:
- Recommend which resorts to visit each day
- Consider the 7-day snow forecast for optimal timing
- Factor in weekend traffic patterns (avoid I-70 Sunday eastbound if possible)
- Suggest best departure times to avoid traffic
"""
                if lodging_pref and lodging_pref != "Flexible":
                    trip_prompt += f"- I'm staying in/near: {lodging_pref}\n"

                if trip_notes.strip():
                    trip_prompt += f"- Additional notes: {trip_notes}\n"

                # Add pass restriction with explicit resort list
                if selected_passes and "All" not in selected_passes:
                    pass_str = " and ".join(selected_passes)
                    valid_resorts = [r for r in RESORT_STATIONS if _pass_filter(r, selected_passes)]
                    trip_prompt += f"\n**IMPORTANT**: I have a {pass_str} Pass. You MUST ONLY recommend resorts from this list: {', '.join(valid_resorts)}. Do not recommend any other resorts."
                else:
                    trip_prompt += f"\nMy ski pass(es): Any resort is fine"

                trip_prompt += f"\nStarting from: {city_name}"
                trip_prompt += """

Please provide a day-by-day itinerary in this format:

**Day 1 (Date)** - Resort Name
- Expected snow: X" fresh, Y" base
- Conditions: [weather description]
- Drive time: X hours from [location]
- Departure: Leave by [time] to avoid traffic
- Why: [brief rationale for this choice]

[Continue for each day...]

**Overall Tips:**
[Any additional advice about lodging, traffic, gear, etc.]"""

                # Inject this prompt into the chat
                st.session_state.trip_planner_prompt = trip_prompt
                st.rerun()

    prompt = st.chat_input("Where should I ski this weekend?")

    _chat_container = st.container(height=600, border=False)

    with _chat_container:
        _new_msg_ph = st.empty()

        _old_history = st.session_state.messages

        if not _old_history and not prompt:
            with st.chat_message("assistant"):
                st.markdown(
                    "Hey! I can tell you where the powder is right now, "
                    "which resorts historically get the most snow, and whether "
                    "this season is above or below average. What do you want to know?"
                )

        _pairs = list(zip(_old_history[0::2], _old_history[1::2]))
        for user_msg, asst_msg in reversed(_pairs):
            with st.chat_message(user_msg["role"]):
                st.markdown(user_msg["content"])
            with st.chat_message(asst_msg["role"]):
                st.markdown(asst_msg["content"])

# ── Handle new prompt — data must be loaded ───────────────────────────────────

# Check for trip planner prompt
if "trip_planner_prompt" in st.session_state and not _first_load:
    prompt = st.session_state.trip_planner_prompt
    del st.session_state.trip_planner_prompt

if prompt and not _first_load:
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Detect if this is a trip planning query
    _is_trip_plan = any(keyword in prompt.lower() for keyword in ["trip", "itinerary", "day-by-day", "multi-day", "days starting"])

    # Build live conditions snapshot for all resorts (unrounded so agent is precise)
    _cond_snapshot = "\n".join(
        f"  - {r}: {conditions[r].get('new_snow_72h', 0):.1f}\" new (72h), "
        f"{conditions[r].get('new_snow_48h', 0):.1f}\" new (48h), "
        f"{conditions[r].get('new_snow_24h', 0):.1f}\" new (24h), "
        f"{conditions[r].get('snow_depth_in', 0):.1f}\" base"
        if conditions.get(r) else f"  - {r}: no live data"
        for r in RESORT_STATIONS
    )

    # Build forecast snapshot (enhanced for trip planning)
    if _is_trip_plan:
        # Load full 7-day forecast
        forecasts_7day = load_7day_forecasts()
        _forecast_lines = []
        for r in RESORT_STATIONS:
            if forecasts_7day.get(r):
                daily = " / ".join([f"{f['date'][-5:]}: {f['snowfall_in']:.1f}\"" for f in forecasts_7day[r]])
                _forecast_lines.append(f"  - {r}: {daily}")
            else:
                _forecast_lines.append(f"  - {r}: no forecast")
        _forecast_snapshot = "\n".join(_forecast_lines)
        _forecast_label = "7-day snowfall forecast (Open-Meteo)"
    else:
        _forecast_snapshot = "\n".join(
            f"  - {r}: Sat {forecasts[r]['saturday_snow_in']:.1f}\" / "
            f"Sun {forecasts[r]['sunday_snow_in']:.1f}\" / "
            f"weekend total {forecasts[r]['weekend_total_in']:.1f}\""
            if forecasts.get(r) else f"  - {r}: no forecast"
            for r in RESORT_STATIONS
        )
        _forecast_label = "Weekend snowfall forecast (Open-Meteo)"

    # Add traffic/distance context for trip planning
    if _is_trip_plan:
        _distance_info = "\n".join(
            f"  - {r}: {_haversine_miles(user_lat, user_lon, RESORT_STATIONS[r]['lat'], RESORT_STATIONS[r]['lon']):.0f} mi from {city_name}"
            for r in RESORT_STATIONS
        )
        _traffic_tips = """
[Traffic patterns to consider:]
  - Saturday AM westbound I-70: heavy 6-10am (leave early or late)
  - Sunday PM eastbound I-70: very heavy 1-6pm (leave before noon or after 7pm)
  - US-40 and US-285 are slower but less crowded alternatives
  - Chain laws can add 30-60min delay during storms"""

        _context = (
            f"[Live snowpack for all resorts right now:\n{_cond_snapshot}]\n\n"
            f"[{_forecast_label}:\n{_forecast_snapshot}]\n\n"
            f"[Distances from {city_name}:\n{_distance_info}]\n\n"
            f"{_traffic_tips}\n\n"
        )
    else:
        _context = (
            f"[Live snowpack for all resorts right now:\n{_cond_snapshot}]\n\n"
            f"[{_forecast_label}:\n{_forecast_snapshot}]\n\n"
        )

    if selected_passes and "All" not in selected_passes:
        pass_str = " and ".join(selected_passes)
        pass_resorts = [r for r in RESORT_STATIONS
                        if _pass_filter(r, selected_passes)]
        agent_prompt = (
            _context
            + f"[User context: I have a {pass_str} Pass. "
            f"Only recommend resorts on my pass: {', '.join(pass_resorts)}.]\n\n"
            + prompt
        )
    else:
        agent_prompt = _context + prompt

    # Write new exchange into the top placeholder inside _chat_container
    with _new_msg_ph.container():
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Checking the snowpack..."):
                print(f"\n\033[1mQuestion:\033[0m {prompt}")

                # Pass the last 3 exchanges (6 messages) as conversation memory.
                # Older turns are dropped to keep context costs bounded.
                # Only the current question gets the full live snapshot injected.
                # exclude just-appended user msg
                _history = st.session_state.messages[:-1]
                # last 3 exchanges = 6 messages
                _recent = _history[-6:]
                _conv = [
                    ("human" if m["role"] ==
                     "user" else "assistant", m["content"])
                    for m in _recent
                ]
                _conv.append(("human", agent_prompt))
                result = st.session_state.agent.invoke({"messages": _conv})
                response = result["messages"][-1].content

            # Extract hidden [RANKING: ...] line and strip it from displayed text
            _ranking_match = re.search(r'\[RANKING:\s*([^\]]+)\]', response)
            response_display = re.sub(
                r'\s*\[RANKING:[^\]]+\]', '', response).strip()
            st.markdown(response_display)

    st.session_state.messages.append(
        {"role": "assistant", "content": response_display})

    # Update AI Pick ranking from the explicit hidden ranking line
    if _ranking_match:
        _ranked = [r.strip() for r in _ranking_match.group(1).split(',')]
        # Ensure all resorts are present (append any the agent omitted)
        for r in RESORT_STATIONS:
            if r not in _ranked:
                _ranked.append(r)
    else:
        # Fallback: mention-order
        _lower = response.lower()
        _mentioned = sorted(
            [(r, _lower.index(r.lower()))
             for r in RESORT_STATIONS if r.lower() in _lower],
            key=lambda x: x[1]
        )
        _ranked = [r for r, _ in _mentioned]
        for r in RESORT_STATIONS:
            if r not in _ranked:
                _ranked.append(r)
    st.session_state["ai_pick_ranking"] = _ranked

    # Rerun so the left column reflects the new ranking immediately
    if sort_by == "🤖 AI Pick":
        st.rerun()

# ── First load: fetch data, fill cards placeholder, then rerun to show map ────

if _first_load:
    with _TPE(max_workers=2) as _pool:
        _f_cond = _pool.submit(load_conditions)
        _f_fore = _pool.submit(load_forecasts)
        st.session_state.conditions = _f_cond.result()
        st.session_state.forecasts  = _f_fore.result()

    conditions = st.session_state.conditions
    forecasts  = st.session_state.forecasts

    # Compute cards with seed widget values (Denver / Fresh Snow / All)
    _visible_fl = {r: d for r, d in conditions.items() if _pass_filter(r, selected_passes)}
    _use_base_fl = sort_by == "🏔️ Base Snow"
    _field_fl   = "snow_depth_in" if _use_base_fl else "new_snow_72h"
    _floor_fl   = 30 if _use_base_fl else 6
    _vals_fl    = [_visible_fl[r].get(_field_fl, 0) if _visible_fl[r] else 0 for r in _visible_fl]
    _CMAX_fl    = max(max(_vals_fl, default=0), _floor_fl)

    # Default sort: fresh snow descending
    _ordered_fl = sorted(
        _visible_fl.items(),
        key=lambda x: -(x[1].get("new_snow_72h", 0) if x[1] else 0)
    )

    _cards_fl = []
    for resort, d in _ordered_fl:
        badges = " ".join(_PASS_BADGE[p] for p in _resort_passes(resort))
        dist = _haversine_miles(
            user_lat, user_lon,
            RESORT_STATIONS[resort]["lat"], RESORT_STATIONS[resort]["lon"]
        )
        if d is None:
            _cards_fl.append(
                f'<div class="resort-card">'
                f'<div class="resort-card-top">'
                f'<span class="resort-dot" style="color:#5a8fb5">○</span>'
                f'<span class="resort-name">{resort}</span>{badges}'
                f'<span class="resort-dist">{dist:.0f} mi</span>'
                f'</div>'
                f'<div class="resort-no-data">no SNOTEL — check resort site</div>'
                f'</div>'
            )
            continue
        new72 = d.get("new_snow_72h", 0)
        base  = d.get("snow_depth_in", 0)
        _val  = base if _use_base_fl else new72
        _t    = (_val / _CMAX_fl) if _CMAX_fl > 0 else 0
        _cards_fl.append(
            f'<div class="resort-card">'
            f'<div class="resort-card-top">'
            f'<span class="resort-dot" style="color:{_blues_color(_t)}">●</span>'
            f'<span class="resort-name">{resort}</span>{badges}'
            f'<span class="resort-dist">{dist:.0f} mi</span>'
            f'</div>'
            f'<div class="resort-stats">{new72:.0f}" new (72h) · {base:.0f}" base</div>'
            f'</div>'
        )

    _cards_ph.markdown("".join(_cards_fl), unsafe_allow_html=True)
    st.rerun()
