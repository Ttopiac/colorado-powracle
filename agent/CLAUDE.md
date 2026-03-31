# agent/ — LangChain Agent

## What lives here
- `agent.py` — `build_agent()` factory function
- `chat_service.py` — `run_chat_turn()` shared helper (used by both `app.py` and `api.py`)
- `prompts.py` — `SYSTEM_PROMPT` string

## agent.py — build_agent(verbose=False)
Returns a LangChain agent using `create_agent()` from `langchain.agents`.

```python
llm = ChatOpenAI(
    model_name="anthropic/claude-3-haiku",
    temperature=0,
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",   # OpenRouter proxy
)
```

**Why OpenRouter?** Routes to Claude 3 Haiku at lower cost than direct Anthropic API. Uses the `langchain-openai` compatible interface.

**`_PrettyCallback`** — custom callback handler that prints Thought/Action/Observation in colored terminal output when `verbose=True`. Safely handles malformed LLM output via try/except around `ast.literal_eval`.

**Current tools list** (order matters for agent priority):
1. `current_snowpack_tool`
2. `historical_snowpack_tool`
3. `web_search_tool`
4. `live_traffic_tool`
5. `best_departure_tool`
6. `snow_forecast_tool`

### Adding a tool
```python
# 1. Import from tools/
from tools.my_module import my_tool

# 2. Add to the list in build_agent()
tools=[
    current_snowpack_tool,
    historical_snowpack_tool,
    web_search_tool,
    live_traffic_tool,
    best_departure_tool,
    my_tool,              # ← add here
],
```
Then update `SYSTEM_PROMPT` in `prompts.py`.

## prompts.py

`SYSTEM_PROMPT` is injected as the agent prefix — the LLM sees it before every conversation turn.

### Current sections in SYSTEM_PROMPT
1. **Tool usage guidance** — when to call each tool, in what order
2. **Resort knowledge** — all 19 resorts organized by pass (IKON/EPIC/INDY), with corridor and snow characteristic notes
3. **Snowpack science** — SWE interpretation, powder thresholds (≥6" new in 24h = powder day), aspect knowledge
4. **Traffic patterns** — I-70 Saturday westbound 6–10 AM peak, Sunday eastbound 1–5 PM peak
5. **Decision logic** — prefer non-I-70 resorts when congestion is high; cross-reference snow + traffic

### When to update SYSTEM_PROMPT
- Adding a new tool: add a knowledge block explaining when to use it and what it returns
- Adding a new resort: add to the resort list with its corridor and pass
- Observing the agent making systematic errors: add a corrective rule

## app.py integration
The Streamlit app injects context before each agent call:
- Live snowpack snapshot for all 19 resorts
- Weekend forecast snapshot (or full 7-day forecast for trip planning queries)
- Pass filter restrictions (if user has selected IKON/EPIC/INDY)
- Last 3 conversation exchanges as memory
- For trip planner: distances from starting city + traffic tips

## LangChain version notes
Uses `langchain-classic==1.0.1` — a compatibility layer for LangChain 1.x API.
`create_agent` is imported from `langchain.agents`.
Do **not** upgrade `langchain` or `langchain-classic` without full regression testing — the agent API changed significantly.
