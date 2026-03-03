# agent/ — LangChain Agent

## What lives here
- `agent.py` — `build_agent()` factory function
- `prompts.py` — `SYSTEM_PROMPT` string

## agent.py

### build_agent(verbose=False)
Returns a LangChain `AgentExecutor` using the `zero-shot-react-description` strategy.

```python
llm = ChatOpenAI(
    model_name="anthropic/claude-3-haiku",
    temperature=0,
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",   # OpenRouter proxy
)
```

**Why OpenRouter?** Routes to Claude 3 Haiku at lower cost than direct Anthropic API. Uses the `langchain-openai` compatible interface.

**`handle_parsing_errors=True`** — prevents the agent from crashing on malformed LLM output; it retries automatically.

**Current tools list** (order matters for agent priority):
1. `current_snowpack_tool`
2. `historical_snowpack_tool`
3. `web_search_tool`
4. `live_traffic_tool`
5. `best_departure_tool`

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

## LangChain version notes
Uses `langchain-classic==1.0.1` — a compatibility layer for LangChain 1.x API.
`initialize_agent` and `AgentExecutor` are imported from `langchain` (not `langchain_core`).
Do **not** upgrade to LangChain 0.2+ without testing — the agent API changed significantly.
