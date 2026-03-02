"""
Tool 3: web_search — SerpAPI for live resort reports, road conditions, lift status.
"""

from pathlib import Path
from dotenv import load_dotenv
from langchain_community.utilities import SerpAPIWrapper
from langchain_classic.tools import Tool

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
search = SerpAPIWrapper()

web_search_tool = Tool(
    name="web_search",
    func=search.run,
    description=(
        "Search the web for current ski resort snow reports, lift opening status, "
        "I-70 road conditions, chain laws, or any real-time information not in the database. "
        "Good queries: '[resort] snow report today', 'I-70 conditions today', "
        "'[resort] lift status'."
    ),
)
