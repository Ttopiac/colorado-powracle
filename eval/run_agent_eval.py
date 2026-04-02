"""
Run the current Colorado Powracle system on the benchmark prompt set.

Usage:
    python eval/run_agent_eval.py
    python eval/run_agent_eval.py --limit 5
    python eval/run_agent_eval.py --use-deterministic-simple-answers

This script:
- reads eval/prompts.csv
- calls the current local system through api.ChatRequest -> api.chat
- writes outputs to eval/results/current_agent_outputs_<timestamp>.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from api import ChatRequest, chat


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = ROOT / "eval" / "deterministic_answers_eval.csv"
RESULTS_DIR = ROOT / "eval" / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Optional limit on number of prompts to run")
    parser.add_argument(
        "--use-deterministic-simple-answers",
        action="store_true",
        help="Enable the optional deterministic path for simple factual questions",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="current_agent_outputs",
        help="Prefix for the output filename",
    )
    return parser.parse_args()


def parse_selected_passes(value: str) -> list[str]:
    if not value:
        return ["All"]

    raw = value.strip()
    if raw.lower() == "all":
        return ["All"]

    for sep in ("|", ",", ";"):
        if sep in raw:
            return [part.strip() for part in raw.split(sep) if part.strip()]

    return [raw]


def load_prompts(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def run_one_prompt(row: dict[str, str], use_deterministic_simple_answers: bool) -> dict[str, Any]:
    selected_passes = parse_selected_passes(row.get("selected_passes", "All"))
    start_city = row.get("start_city", "Denver") or "Denver"
    question = row["question"]

    request = ChatRequest(
        question=question,
        messages=[],
        selected_passes=selected_passes,
        start_city=start_city,
        use_deterministic_simple_answers=use_deterministic_simple_answers,
    )

    response = chat(request)

    return {
        "id": row.get("id"),
        "category": row.get("category"),
        "question": question,
        "selected_passes": selected_passes,
        "start_city": start_city,
        "expected_type": row.get("expected_type"),
        "notes": row.get("notes"),
        "use_deterministic_simple_answers": use_deterministic_simple_answers,
        "answer": response.answer,
        "ranking": response.ranking,
        "raw_response": response.raw_response,
    }


def main() -> None:
    args = parse_args()

    if not PROMPTS_PATH.exists():
        raise FileNotFoundError(f"Could not find prompts file at {PROMPTS_PATH}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    prompts = load_prompts(PROMPTS_PATH)
    if args.limit is not None:
        prompts = prompts[: args.limit]

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    print(f"Loaded {len(prompts)} prompts from {PROMPTS_PATH}")
    print(f"Deterministic simple answers enabled: {args.use_deterministic_simple_answers}")

    for i, row in enumerate(prompts, start=1):
        prompt_id = row.get("id", f"row_{i}")
        question = row.get("question", "")
        print(f"[{i}/{len(prompts)}] {prompt_id}: {question}")

        try:
            result = run_one_prompt(
                row,
                use_deterministic_simple_answers=args.use_deterministic_simple_answers,
            )
            results.append(result)
        except Exception as e:
            errors.append(
                {
                    "id": prompt_id,
                    "question": question,
                    "error": repr(e),
                }
            )
            print(f"  ERROR: {e!r}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "deterministic_on" if args.use_deterministic_simple_answers else "deterministic_off"
    output_path = RESULTS_DIR / f"{args.output_prefix}_{suffix}_{timestamp}.json"

    payload = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "prompt_count": len(prompts),
            "success_count": len(results),
            "error_count": len(errors),
            "use_deterministic_simple_answers": args.use_deterministic_simple_answers,
            "source_prompts": str(PROMPTS_PATH),
        },
        "results": results,
        "errors": errors,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print()
    print(f"Wrote results to {output_path}")
    print(f"Successful: {len(results)}")
    print(f"Errors: {len(errors)}")


if __name__ == "__main__":
    main()
