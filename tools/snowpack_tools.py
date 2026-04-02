"""
LangChain tools for snowpack data.
Tool 1: get_current_snowpack  — live SNOTEL API
Tool 2: get_snowpack_history  — historical DuckDB query
"""

from pathlib import Path
import duckdb
from langchain_classic.tools import Tool
from ingestion.snotel_live import fetch_current_snowpack
from resorts import RESORT_STATIONS

DB_PATH = str(Path(__file__).resolve().parent.parent / "powder_oracle.duckdb")
RESORT_LIST = ", ".join(RESORT_STATIONS.keys())


def _clean(s: str) -> str:
    """Strip whitespace and any surrounding quotes the LLM may have added."""
    return s.strip().strip("'\"`")


# ── Tool 1: live snowpack ─────────────────────────────────────────────────────

def _current_snowpack(resort_name: str) -> str:
    resort_name = _clean(resort_name)
    info = RESORT_STATIONS.get(resort_name)

    # Fuzzy match: find first resort whose name contains the input
    if not info:
        for name, data in RESORT_STATIONS.items():
            if resort_name.lower() in name.lower():
                resort_name = name
                info = data
                break

    if not info:
        return f"Unknown resort '{resort_name}'. Valid options: {RESORT_LIST}"

    quality = info.get("snotel_quality", "good")

    if quality == "none" or not info.get("station_id"):
        return (
            f"No SNOTEL station within range of {resort_name}. "
            f"Use web_search with query: '{resort_name} snow report today'"
        )

    d = fetch_current_snowpack(info["station_id"])
    emoji = "🔵" if d["new_snow_72h"] >= 12 else ("🟢" if d["new_snow_72h"] >= 6 else "⚪")
    lines = [
        f"{emoji} {resort_name} — live snowpack:",
        f"  Base depth : {d['snow_depth_in']}\" on ground",
        f"  New (24h)  : {d['new_snow_24h']}\"",
        f"  New (48h)  : {d['new_snow_48h']}\"",
        f"  New (72h)  : {d['new_snow_72h']}\"",
        f"  Snow water : {d['swe_in']}\" SWE",
    ]
    if quality == "fair":
        lines.append(
            f"  (proxy: {info['station_name']} SNOTEL — "
            f"cross-check with {resort_name} snow report for precision)"
        )
    return "\n".join(lines)


current_snowpack_tool = Tool(
    name="get_current_snowpack",
    func=_current_snowpack,
    description=(
        "Returns live snowpack conditions (base depth, new snow in last 24/48/72 hours) "
        "for a single named Colorado ski resort. Call this ONLY for questions about live or "
        "current conditions for one specific resort. Do NOT call for historical comparisons, "
        "averages, 'historically', 'most snow in [month]', 'best month', or 'year over year' "
        "questions — use get_snowpack_history for those instead. "
        f"Valid resort names: {RESORT_LIST}."
    ),
)


# ── Tool 2: historical snowpack ───────────────────────────────────────────────

_MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def _snowpack_history(query: str) -> str:
    query = _clean(query).lower()
    try:
        con = duckdb.connect(DB_PATH, read_only=True)

        # Detect resort name for filtered queries
        resort_match = None
        for resort in RESORT_STATIONS.keys():
            if resort.lower() in query:
                resort_match = resort
                break

        # Detect specific month name in query
        month_num = next((i + 1 for i, m in enumerate(_MONTH_NAMES) if m in query), None)

        if any(w in query for w in ["consistent", "reliable", "every year", "best resort overall"]):
            sql = """
                SELECT resort,
                       ROUND(AVG(peak_depth_in), 1)    AS avg_peak_depth_in,
                       ROUND(STDDEV(peak_depth_in), 1) AS consistency_stddev,
                       COUNT(*)                        AS seasons_of_data
                FROM season_summary
                GROUP BY resort
                ORDER BY consistency_stddev ASC
            """
        elif any(w in query for w in ["above average", "below average", "this year",
                                      "this season", "season compare"]):
            from datetime import date
            this_year = date.today().year
            resort_clause = f"AND s.resort = '{resort_match}'" if resort_match else ""
            sql = f"""
                SELECT s.resort,
                       s.year,
                       s.peak_depth_in          AS this_season_peak_in,
                       h.avg_peak               AS historical_avg_in,
                       ROUND(s.peak_depth_in - h.avg_peak, 1) AS diff_from_avg_in
                FROM season_summary s
                JOIN (
                    SELECT resort, ROUND(AVG(peak_depth_in), 1) AS avg_peak
                    FROM season_summary GROUP BY resort
                ) h ON s.resort = h.resort
                WHERE s.year = {this_year} {resort_clause}
                ORDER BY diff_from_avg_in DESC
            """
        elif any(w in query for w in ["same time", "this month", "time of year",
                                      "compared to", "normal for", "last year",
                                      "year ago", "typical"]):
            # Month-specific: compare current month's historical averages
            from datetime import date
            this_month = date.today().month
            resort_clause = f"AND resort = '{resort_match}'" if resort_match else ""
            sql = f"""
                SELECT resort, month,
                       ROUND(avg_depth_in, 1)        AS historical_avg_depth_in,
                       ROUND(avg_daily_new_snow, 1)  AS historical_avg_daily_new_in
                FROM monthly_averages
                WHERE month = {this_month} {resort_clause}
                ORDER BY historical_avg_depth_in DESC
            """
        else:
            # Default: monthly average new snow — useful for "best month to ski X"
            # or "which resort gets most snow in January" (month_num detected above)
            conditions = []
            if resort_match:
                conditions.append(f"resort = '{resort_match}'")
            if month_num:
                conditions.append(f"month = {month_num}")
            where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"""
                SELECT resort, month,
                       avg_depth_in,
                       avg_daily_new_snow AS avg_daily_new_in
                FROM monthly_averages
                {where_clause}
                ORDER BY avg_daily_new_snow DESC
                LIMIT 25
            """

        df = con.execute(sql).fetchdf()
        con.close()
        return df.to_string(index=False)

    except Exception as e:
        return f"Database error: {e}. Make sure db/setup.py has been run."


historical_snowpack_tool = Tool(
    name="get_snowpack_history",
    func=_snowpack_history,
    description=(
        "Queries 10 years of historical SNOTEL snowpack data stored in DuckDB. "
        "Use for: which resort historically gets the most snow, is this season above/below average, "
        "which resort is most consistent year over year, best month to ski, "
        "how does current snowpack compare to typical/normal/last year for this time of year. "
        "Input: a natural language question about historical snow patterns (resort name optional)."
    ),
)
