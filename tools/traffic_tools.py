"""
LangChain tools for traffic data.
Tool 4: get_live_traffic       — COTRIP API (live incidents + road conditions)
Tool 5: get_best_departure_time — historical DuckDB traffic_patterns query
"""

from pathlib import Path
import duckdb
from langchain_classic.tools import Tool
from ingestion.cotrip_live import summarise_corridor

DB_PATH = str(Path(__file__).resolve().parent.parent / "powder_oracle.duckdb")


def _clean(s: str) -> str:
    """Strip whitespace and any surrounding quotes the LLM may have added."""
    return s.strip().strip("'\"`")


# Day-of-week name → integer (Monday = 0, Sunday = 6)
_DOW = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "nov": 11, "dec": 12,
}

# Corridors the tool recognises
_CORRIDORS = {
    "i-70":   "I-70",
    "i70":    "I-70",
    "us-40":  "US-40",
    "us40":   "US-40",
    "us-285": "US-285",
    "us285":  "US-285",
}


# ── Tool 4: live traffic ──────────────────────────────────────────────────────

def _live_traffic(corridor_input: str) -> str:
    """
    Fetch live road conditions for the specified corridor.
    Falls back to a web_search suggestion when COTRIP_API_KEY is not set.
    """
    corridor_input = _clean(corridor_input)
    corridor = _CORRIDORS.get(corridor_input.lower(), corridor_input.upper())

    summary = summarise_corridor(corridor)
    if summary is not None:
        return summary

    # No API key — instruct agent to use web_search
    return (
        f"COTRIP API key not configured. "
        f"To check {corridor} conditions, use web_search with a query like: "
        f'"{corridor} road conditions today" or "COTRIP {corridor}".'
    )


live_traffic_tool = Tool(
    name="get_live_traffic",
    func=_live_traffic,
    description=(
        "Returns current road conditions and incidents for a Colorado mountain corridor. "
        "Input: corridor name — one of 'I-70', 'US-40', 'US-285', 'US-550'. "
        "Reports chain laws, closures, accidents, and surface conditions. "
        "Call this when the user asks about current road conditions or whether I-70 is open."
    ),
)


# ── Tool 5: best departure time ───────────────────────────────────────────────

def _best_departure_time(query: str) -> str:
    """
    Query traffic_patterns view for the best departure windows on a given corridor/day.
    Input is a natural-language description, e.g. 'I-70 this Saturday in January'.
    """
    q = _clean(query).lower()

    # --- Parse corridor ---
    corridor = "I-70"   # default
    for key, val in _CORRIDORS.items():
        if key in q:
            corridor = val
            break

    # --- Parse day of week ---
    dow = 5   # default: Saturday (most common question)
    for name, num in _DOW.items():
        if name in q:
            dow = num
            break

    # --- Parse month ---
    month_filter = ""
    for name, num in _MONTH_NAMES.items():
        if name in q:
            month_filter = f"AND month = {num}"
            break

    # --- Holiday flag ---
    is_holiday = any(w in q for w in ["holiday", "presidents", "mlk", "christmas",
                                       "thanksgiving", "spring break", "new year"])

    holiday_filter = "AND is_holiday_weekend = TRUE" if is_holiday else ""

    # --- Direction logic ---
    # For departure (going to resort), focus on westbound morning
    # For return, focus on eastbound afternoon
    if any(w in q for w in ["return", "coming back", "eastbound", "sunday"]) and dow == 6:
        direction = "eastbound"
        peak_note = "afternoon eastbound traffic peaks Sunday 1–5pm"
    else:
        direction = "westbound"
        peak_note = "morning westbound traffic peaks Saturday 6–10am"

    try:
        con = duckdb.connect(DB_PATH, read_only=True)

        # Check if traffic_patterns view exists
        views = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_type = 'VIEW'"
        ).fetchall()]

        if "traffic_patterns" not in views:
            con.close()
            return (
                "Traffic history not loaded yet. "
                "Run: python ingestion/cdot_historical.py && python db/setup.py"
            )

        # Use the chokepoint sensor (highest AADT) as the representative for the corridor.
        # For I-70 that's Idaho Springs (MP240); for US-40 it's Berthoud Pass.
        location_filter = {
            "I-70":   "AND location_name = 'I-70 @ Idaho Springs'",
            "US-40":  "AND location_name = 'US-40 @ Berthoud Pass'",
        }.get(corridor, "")

        sql = f"""
            SELECT
                hour,
                ROUND(AVG(avg_volume), 0) AS avg_vehicles_per_hour
            FROM traffic_patterns
            WHERE corridor   = '{corridor}'
              AND direction   = '{direction}'
              AND day_of_week = {dow}
              {location_filter}
              {month_filter}
              {holiday_filter}
            GROUP BY hour
            ORDER BY hour
        """
        df = con.execute(sql).fetchdf()
        con.close()

        if df.empty:
            return (
                f"No historical traffic data for {corridor} {direction} on "
                f"{_DAY_NAMES[dow]}. Try a different day or corridor."
            )

        # Find the 3 lowest-volume hours (best departure windows)
        best = df.nsmallest(3, "avg_vehicles_per_hour").sort_values("hour")
        worst = df.nlargest(3, "avg_vehicles_per_hour").sort_values("hour")

        lines = [
            f"Historical {corridor} {direction} traffic on {_DAY_NAMES[dow]}:",
            f"({peak_note})\n",
            "Best departure windows (lowest congestion):",
        ]
        for _, row in best.iterrows():
            h = int(row["hour"])
            ampm = f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"
            lines.append(f"  ✅ {ampm} — ~{int(row['avg_vehicles_per_hour']):,} vehicles/hr")

        lines.append("\nWindows to avoid (heaviest congestion):")
        for _, row in worst.iterrows():
            h = int(row["hour"])
            ampm = f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"
            lines.append(f"  ⚠️  {ampm} — ~{int(row['avg_vehicles_per_hour']):,} vehicles/hr")

        if is_holiday:
            lines.append(
                "\nNote: Holiday weekend — expect 30–50% higher volume than typical weekends."
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Database error: {e}. Make sure db/setup.py has been run."


best_departure_tool = Tool(
    name="get_best_departure_time",
    func=_best_departure_time,
    description=(
        "Returns the best times to depart to avoid traffic congestion, "
        "based on 10 years of historical I-70 corridor traffic patterns. "
        "Input: natural language description of corridor and day, e.g. "
        "'I-70 Saturday in January', 'US-40 Sunday morning', "
        "'I-70 Presidents Day weekend Saturday'. "
        "Call this when the user asks what time to leave or how to avoid traffic."
    ),
)
