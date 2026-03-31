import re
from typing import Any


def run_chat_turn(agent: Any, messages: list[dict], agent_prompt: str, resort_names: list[str]) -> dict:
    """
    Shared helper for one chat turn.

    Inputs:
      - agent: the already-built LangChain agent
      - messages: Streamlit-style message history, e.g.
          [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
      - agent_prompt: the fully prepared prompt for the current turn
      - resort_names: list of all resort names, used to build ranking

    Returns:
      {
        "response_display": cleaned text to show the user,
        "ranking": ordered resort list,
        "raw_response": raw model response
      }
    """

    # Exclude the just-appended current user message, matching current app.py behavior
    history = messages[:-1]

    # Keep only the last 3 exchanges = 6 messages
    recent = history[-6:]

    conv = [
        ("human" if m["role"] == "user" else "assistant", m["content"])
        for m in recent
    ]
    conv.append(("human", agent_prompt))

    result = agent.invoke({"messages": conv})
    raw_response = result["messages"][-1].content

    # Extract hidden ranking tag
    ranking_match = re.search(r"\[RANKING:\s*([^\]]+)\]", raw_response)

    # Remove ranking tag from displayed answer
    response_display = re.sub(r"\s*\[RANKING:[^\]]+\]", "", raw_response).strip()

    if ranking_match:
        ranked = [r.strip() for r in ranking_match.group(1).split(",")]
        for r in resort_names:
            if r not in ranked:
                ranked.append(r)
    else:
        lower = raw_response.lower()
        mentioned = sorted(
            [(r, lower.index(r.lower())) for r in resort_names if r.lower() in lower],
            key=lambda x: x[1],
        )
        ranked = [r for r, _ in mentioned]
        for r in resort_names:
            if r not in ranked:
                ranked.append(r)

    return {
        "response_display": response_display,
        "ranking": ranked,
        "raw_response": raw_response,
    }
