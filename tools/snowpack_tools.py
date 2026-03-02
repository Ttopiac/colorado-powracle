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
        "for a named Colorado ski resort. Call this for any question about current snow. "
        f"Valid resort names: {RESORT_LIST}."
    ),
)


# ── Tool 2: historical snowpack ───────────────────────────────────────────────

def _snowpack_history(query: str) -> str:
    query = _clean(query).lower()
    try:
        con = duckdb.connect(DB_PATH, read_only=True)

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
                                      "this season", "compared to"]):
            from datetime import date
            this_year = date.today().year
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
                WHERE s.year = {this_year}
                ORDER BY diff_from_avg_in DESC
            """
        else:
            # Default: monthly average new snow — useful for "best month to ski X"
            sql = """
                SELECT resort, month,
                       avg_depth_in,
                       avg_daily_new_snow AS avg_daily_new_in
                FROM monthly_averages
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
        "which resort is most consistent year over year, best month to ski. "
        "Input: a natural language question about historical snow patterns."
    ),
)
