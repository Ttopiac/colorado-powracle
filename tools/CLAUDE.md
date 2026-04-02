# tools/ — LangChain Tool Definitions

## What lives here
Each file wraps one or more data-fetching functions as LangChain `Tool` objects that the agent can call.

## Current tools

### snowpack_tools.py
| Tool name | LangChain object | Input | Output |
|-----------|-----------------|-------|--------|
| `get_current_snowpack` | `current_snowpack_tool` | Resort name (fuzzy matched) | Formatted string: base depth, SWE, new snow 24/48/72h |
| `get_snowpack_history` | `historical_snowpack_tool` | Natural language query | Query-dependent: monthly avgs, season comparison, or consistency ranking |

**Routing logic in `get_snowpack_history`:**
- Keywords `consistent` / `reliable` → orders by STDDEV (lowest = most consistent)
- Keywords `above average` / `below average` / `this season` → compares current year vs 10yr avg
- Keywords `same time` / `typical` / `last year` → current month's historical averages
- Default → monthly averages for "best month to ski X" queries; if a month name is detected (e.g. "january"), filters to that specific month

**Resort name matching:** `_clean()` strips whitespace and surrounding quotes from LLM input, then does case-insensitive substring match against `RESORT_STATIONS` keys (e.g., `"steamboat"` matches `"Steamboat Springs"`).

### search_tools.py
| Tool name | LangChain object | Input | Output |
|-----------|-----------------|-------|--------|
| `web_search` | `web_search_tool` | Search query string | SerpAPI result (lift status, road conditions, forecasts) |

### traffic_tools.py
| Tool name | LangChain object | Input | Output |
|-----------|-----------------|-------|--------|
| `get_live_traffic` | `live_traffic_tool` | Corridor name (I-70, US-40, US-285, US-550) | Incidents + road conditions string from COtrip API |
| `get_best_departure_time` | `best_departure_tool` | Natural language (e.g., "I-70 Saturday in January") | Best 3 and worst 3 departure windows with volume numbers |

### forecast_tools.py
| Tool name | LangChain object | Input | Output |
|-----------|-----------------|-------|--------|
| `get_snow_forecast` | `snow_forecast_tool` | Resort name (fuzzy matched) | 7-day daily snowfall in inches with weekend days highlighted and weekend total |

**Source:** Open-Meteo API (`https://api.open-meteo.com/v1/forecast`) — no API key required.
**Snowfall conversion:** Open-Meteo returns cm; multiplied by 0.3937 to convert to inches.

**`get_best_departure_time` parsing:**
- Extracts day-of-week, month, holiday flag from free text
- Determines direction: Saturday → westbound (to resorts), Sunday → eastbound (returning)
- Queries `traffic_patterns` DuckDB view grouped by hour, sorts by avg_volume

## How to add a new tool

1. Create or add to a file in `tools/`.
2. Define a plain Python function that takes a string and returns a string.
3. Wrap it:
   ```python
   from langchain_classic.tools import Tool

   my_tool = Tool(
       name="tool_name",           # agent uses this to select the tool
       func=my_function,
       description="One sentence describing when to use this tool and what it returns."
   )
   ```
4. Import the tool object in `agent/agent.py` and add it to the `tools=[]` list in `build_agent()`.
5. Add a knowledge block to `SYSTEM_PROMPT` in `agent/prompts.py` so the agent knows when to reach for it.
6. Update the tools table in `CLAUDE.md` (root) and `docs/AGENTS.md`.

## Constraints
- Tool functions must accept a single `str` argument (LangChain requirement for `zero-shot-react-description`).
- If a tool needs multiple parameters, accept a JSON string or a comma-separated string and parse it inside.
- All tool functions should return a non-empty string — never `None`. Return a graceful "no data" message on failure.
- If a live API key is missing (e.g., `COTRIP_API_KEY`), fall back gracefully and instruct the agent to use `web_search` instead.
