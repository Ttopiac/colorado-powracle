"""
Agent factory. Import build_agent() from here.
"""

import ast
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from tools.snowpack_tools import current_snowpack_tool, historical_snowpack_tool
from tools.search_tools import web_search_tool
from tools.traffic_tools import live_traffic_tool, best_departure_tool
from tools.forecast_tools import snow_forecast_tool
from agent.prompts import SYSTEM_PROMPT

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_CYAN  = "\033[36m"
_AMBER = "\033[33m"
_GREEN = "\033[32m"
_BOLD  = "\033[1m"
_RESET = "\033[0m"


class _PrettyCallback(BaseCallbackHandler):
    """Prints agent activity in a readable format similar to the old AgentExecutor output."""

    def __init__(self):
        self._depth = 0

    def on_chain_start(self, serialized, inputs, **kwargs):
        self._depth += 1
        if self._depth == 1:
            print(f"\n{_BOLD}> Entering new agent chain...{_RESET}")

    def on_chain_end(self, outputs, **kwargs):
        self._depth -= 1
        if self._depth == 0:
            print(f"{_BOLD}> Finished chain.{_RESET}\n")

    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = (serialized or {}).get("name", "tool")
        # input_str arrives as a Python-repr dict like "{'__arg1': 'Vail'}"
        try:
            parsed = ast.literal_eval(input_str)
            clean = parsed.get("__arg1", input_str) if isinstance(parsed, dict) else input_str
        except Exception:
            clean = input_str
        print(f"\n{_CYAN}Action:{_RESET} {tool_name}")
        print(f"{_CYAN}Action Input:{_RESET} {clean}")

    def on_tool_end(self, output, **kwargs):
        out = output.content if hasattr(output, "content") else str(output)
        if len(out) > 600:
            out = out[:600] + "  ...[truncated]"
        print(f"{_AMBER}Observation:{_RESET} {out}")

    def on_llm_end(self, response, **kwargs):
        for chunk in response.generations:
            for gen in chunk:
                msg = getattr(gen, "message", None)
                if not msg:
                    continue
                content = msg.content if isinstance(msg.content, str) else ""
                has_tools = bool(getattr(msg, "tool_calls", None))
                if not content.strip():
                    continue
                if has_tools:
                    print(f"\n{_AMBER}Thought:{_RESET} {content.strip()}")
                else:
                    preview = content[:400] + ("..." if len(content) > 400 else "")
                    print(f"\n{_GREEN}Final Answer:{_RESET} {preview}")


def build_agent(verbose: bool = False):
    llm = ChatOpenAI(
        model_name="anthropic/claude-3-haiku",
        temperature=0,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )
    agent = create_agent(
        model=llm,
        tools=[
            current_snowpack_tool,
            historical_snowpack_tool,
            web_search_tool,
            live_traffic_tool,
            best_departure_tool,
            snow_forecast_tool,
            # Phase 3: append location_tools here
        ],
        system_prompt=SYSTEM_PROMPT,
    )
    if verbose:
        agent = agent.with_config(callbacks=[_PrettyCallback()])
    return agent
