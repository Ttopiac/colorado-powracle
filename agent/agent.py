"""
Agent factory. Import build_agent() from here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_classic.agents import initialize_agent
from langchain_openai import ChatOpenAI
from tools.snowpack_tools import current_snowpack_tool, historical_snowpack_tool
from tools.search_tools import web_search_tool
from tools.traffic_tools import live_traffic_tool, best_departure_tool
from tools.forecast_tools import snow_forecast_tool
from agent.prompts import SYSTEM_PROMPT

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def build_agent(verbose: bool = False):
    llm = ChatOpenAI(
        model_name="anthropic/claude-3-haiku",
        temperature=0,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )
    return initialize_agent(
        tools=[
            current_snowpack_tool,
            historical_snowpack_tool,
            web_search_tool,
            live_traffic_tool,
            best_departure_tool,
            snow_forecast_tool,
            # Phase 3: append location_tools here
        ],
        llm=llm,
        agent="zero-shot-react-description",
        verbose=verbose,
        handle_parsing_errors=True,
        agent_kwargs={"prefix": SYSTEM_PROMPT},
    )
