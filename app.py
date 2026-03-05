"""
Colorado Powracle — Streamlit web app.
Run: streamlit run app.py  (from project root, with conda env active)
"""

from agent.agent import build_agent
from ingestion.snotel_live import fetch_current_snowpack
from resorts import RESORT_STATIONS
import plotly.graph_objects as go
import streamlit as st
import sys
import os
import math

# Ensure project root is on sys.path so package imports work when running via streamlit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


st.set_page_config(
    page_title="Colorado Powracle",
    page_icon="⛷️",
    layout="wide"
)

st.markdown("""
<style>
/* Soften the map expander container */
[data-testid="stExpander"] {
    border: 1px solid rgba(99, 179, 237, 0.18) !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.25) !important;
    overflow: hidden;
}
/* Round the Plotly chart itself so the map has soft edges */
[data-testid="stPlotlyChart"] {
    border-radius: 12px;
    overflow: hidden;
}
[data-testid="stPlotlyChart"] > div,
[data-testid="stPlotlyChart"] iframe {
    border-radius: 12px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ── Agent + chat history (once per session) ───────────────────────────────────

if "agent" not in st.session_state:
    st.session_state.agent = build_agent(verbose=True)
    st.session_state.messages = []

# ── Live conditions (refresh every 30 min) ────────────────────────────────────


@st.cache_data(ttl=1800)
def load_conditions():
    out = {}
    for resort, info in RESORT_STATIONS.items():
        if not info.get("station_id"):
            out[resort] = None   # no SNOTEL — shown differently in sidebar
            continue
        try:
            out[resort] = fetch_current_snowpack(info["station_id"])
        except Exception:
            out[resort] = None
    return out


conditions = load_conditions()

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
    "IKON": '<span style="background:#0a2a5c;color:#90caf9;padding:1px 6px;border-radius:4px;font-size:0.72em;font-weight:700;letter-spacing:0.05em">IKON</span>',
    "EPIC": '<span style="background:#2d0a5c;color:#ce93d8;padding:1px 6px;border-radius:4px;font-size:0.72em;font-weight:700;letter-spacing:0.05em">EPIC</span>',
    "INDY": '<span style="background:#0a3318;color:#80cbc4;padding:1px 6px;border-radius:4px;font-size:0.72em;font-weight:700;letter-spacing:0.05em">INDY</span>',
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



# ── Seed session state so map expander can read widget values on first load ───

if "pass_filter" not in st.session_state:
    st.session_state.pass_filter = ["All"]
if "start_city" not in st.session_state:
    st.session_state.start_city = "Denver"
if "sort_by" not in st.session_state:
    st.session_state.sort_by = "🌨️ Fresh Snow"

selected_passes = st.session_state.pass_filter or ["All"]
city_name = st.session_state.start_city
sort_by = st.session_state.sort_by
user_lat, user_lon = _STARTING_CITIES[city_name]

visible = {r: d for r, d in conditions.items() if _pass_filter(r,
                                                               selected_passes)}
vis_names = list(visible.keys())

_use_base_map = sort_by == "🏔️ Base Snow"
_map_field = "snow_depth_in" if _use_base_map else "new_snow_72h"
_map_label = "Base depth (in)" if _use_base_map else "72h snow (in)"
_map_floor = 30 if _use_base_map else 6
_map_scale = 0.2 if _use_base_map else 2

_all_map_vals = [visible[r].get(_map_field, 0) if visible[r] else 0
                 for r in vis_names]
_CMIN = 0
_CMAX = max(max(_all_map_vals, default=0), _map_floor)

# ── Full-width collapsible map ────────────────────────────────────────────────

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
        p_sizes = [max(10, min(36, v * _map_scale + 10)) for v in p_map_vals]
        _pass_data[pass_name] = dict(
            resorts=p_resorts, map_vals=p_map_vals,
            texts=p_texts, sizes=p_sizes, style=style,
        )

    # Layer 1 — pass-colored halos (rendered first, sit underneath)
    for pass_name, d in _pass_data.items():
        fig.add_trace(go.Scattermapbox(
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
            title=dict(text=_map_label, font=dict(color="#0d1b2e", size=11)),
            thickness=12, len=0.55,
            tickfont=dict(color="#0d1b2e", size=10),
            bgcolor="rgba(220,238,255,0.92)",
            bordercolor="#90b8d8",
            borderwidth=1,
        ) if first_colorbar else None
        fig.add_trace(go.Scattermapbox(
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

    fig.add_trace(go.Scattermapbox(
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
        mapbox=dict(
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
    st.plotly_chart(fig, use_container_width=True)

# ── Two-column layout: conditions | chat ─────────────────────────────────────

col_left, col_right = st.columns([1, 1.5], gap="large")

# ── LEFT: controls + live condition cards ────────────────────────────────────

with col_left:
    st.markdown("### ⛷️ Colorado Powracle")

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

    sort_by = st.radio(
        "Sort by:",
        options=["🌨️ Fresh Snow", "🏔️ Base Snow", "📍 Distance", "🤖 AI Pick"],
        horizontal=True,
        key="sort_by",
    )

    st.markdown("---")
    st.markdown("#### ❄️ Live Conditions")

    _cards = st.container(height=520, border=False)

    if sort_by == "🤖 AI Pick":
        if "ai_pick_ranking" in st.session_state:
            _rank_map = {r: i for i, r in enumerate(st.session_state["ai_pick_ranking"])}
            _ordered = sorted(visible.items(), key=lambda x: _rank_map.get(x[0], 999))
        else:
            # No agent response yet — fall back to fresh snow order
            _ordered = sorted(
                visible.items(),
                key=lambda x: -(x[1].get("new_snow_72h", 0) if x[1] else 0)
            )
            st.caption("💬 Ask the Oracle a question to personalise the AI Pick ranking.")
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
            else:  # 🌨️ Fresh Snow
                return -(d.get("new_snow_72h", 0) if d else 0)
        _ordered = sorted(visible.items(), key=_sort_key)

    with _cards:
        for resort, d in _ordered:
            badges = " ".join(_PASS_BADGE[p] for p in _resort_passes(resort))
            dist = _haversine_miles(
                user_lat, user_lon,
                RESORT_STATIONS[resort]["lat"], RESORT_STATIONS[resort]["lon"]
            )
            dist_tag = f'<span style="color:#5a8fb5;font-size:0.82em"> · {dist:.0f} mi</span>'

            if d is None:
                st.markdown(
                    f"⬜ **{resort}** {badges}{dist_tag}  \n"
                    f'<span style="color:#5a8fb5;font-size:0.88em">no SNOTEL — check resort site</span>',
                    unsafe_allow_html=True)
                continue

            new72 = d.get("new_snow_72h", 0)
            base = d.get("snow_depth_in", 0)
            _val = base if _use_base_map else new72
            _t = (_val / _CMAX) if _CMAX > 0 else 0
            icon = f'<span style="color:{_blues_color(_t)};font-size:1.2em;vertical-align:middle">●</span>'
            st.markdown(
                f"{icon} **{resort}** {badges}{dist_tag}  \n"
                f'<span style="font-size:0.88em">{new72:.0f}" new (72h) · {base:.0f}" base</span>',
                unsafe_allow_html=True)

# ── RIGHT: chat ───────────────────────────────────────────────────────────────

with col_right:
    st.markdown("### 💬 Ask the Oracle")
    st.caption(
        "Ask me where to ski, which resort has the best snow, "
        "or how this season compares to average.")

    _chat_container = st.container(height=520, border=False)

    with _chat_container:
        if not st.session_state.messages:
            with st.chat_message("assistant"):
                st.markdown(
                    "Hey! I can tell you where the powder is right now, "
                    "which resorts historically get the most snow, and whether "
                    "this season is above or below average. What do you want to know?"
                )

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("Where should I ski this weekend?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Build live conditions snapshot for all visible resorts
        _cond_snapshot = "\n".join(
            f"  - {r}: {conditions[r].get('new_snow_72h', 0):.0f}\" new (72h), "
            f"{conditions[r].get('new_snow_48h', 0):.0f}\" new (48h), "
            f"{conditions[r].get('new_snow_24h', 0):.0f}\" new (24h), "
            f"{conditions[r].get('snow_depth_in', 0):.0f}\" base"
            if conditions.get(r) else f"  - {r}: no live data"
            for r in RESORT_STATIONS
        )
        _context = f"[Live snowpack for all resorts right now:\n{_cond_snapshot}]\n\n"

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

        with st.chat_message("assistant"):
            with st.spinner("Checking the snowpack..."):
                response = st.session_state.agent.run(agent_prompt)
            st.markdown(response)

        st.session_state.messages.append(
            {"role": "assistant", "content": response})

        # Update AI Pick ranking based on resort mention order in agent response
        _lower = response.lower()
        _mentioned = sorted(
            [(r, _lower.index(r.lower())) for r in RESORT_STATIONS if r.lower() in _lower],
            key=lambda x: x[1]
        )
        _ranked = [r for r, _ in _mentioned]
        for r in vis_names:
            if r not in _ranked:
                _ranked.append(r)
        st.session_state["ai_pick_ranking"] = _ranked

        # Rerun so the left column reflects the new ranking immediately
        if sort_by == "🤖 AI Pick":
            st.rerun()
