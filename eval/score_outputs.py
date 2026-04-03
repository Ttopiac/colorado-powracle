"""
Score Colorado Powracle benchmark outputs, focusing on factual prompts.

Usage:
    python -m eval.score_outputs
    python -m eval.score_outputs --off path/to/off.json --on path/to/on.json

Behavior:
- Picks the "best" deterministic-off and deterministic-on runs from eval/results/
  if explicit paths are not provided.
- Scores factual prompts (F01-F10).
- Writes:
    eval/results/scored_summary.json
    EVAL_SUMMARY.md
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

from resorts import RESORT_STATIONS


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "eval" / "results"
SUMMARY_JSON_PATH = RESULTS_DIR / "scored_summary.json"
SUMMARY_MD_PATH = ROOT / "EVAL_SUMMARY.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--off", type=str, default=None, help="Path to deterministic-off results JSON")
    parser.add_argument("--on", type=str, default=None, help="Path to deterministic-on results JSON")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def choose_best_run(pattern: str) -> Path:
    candidates = [Path(p) for p in glob.glob(str(RESULTS_DIR / pattern))]
    if not candidates:
        raise FileNotFoundError(f"No files matched {pattern} in {RESULTS_DIR}")

    scored: list[tuple[int, float, Path]] = []
    for path in candidates:
        try:
            payload = load_json(path)
            success_count = int(payload.get("meta", {}).get("success_count", 0))
        except Exception:
            success_count = -1
        scored.append((success_count, path.stat().st_mtime, path))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored[0][2]


def get_allowed_resorts(selected_passes: list[str], question: str) -> set[str]:
    q_upper = (question or "").upper()
    explicit_passes = [p for p in ("IKON", "EPIC", "INDY") if p in q_upper]
    effective = explicit_passes if explicit_passes else (selected_passes or ["All"])

    if "All" in effective:
        return set(RESORT_STATIONS.keys())

    allowed = set()
    for resort, info in RESORT_STATIONS.items():
        passes = info.get("pass", [])
        if any(p in passes for p in effective):
            allowed.add(resort)
    return allowed


def ikon_resorts() -> set[str]:
    return {
        resort
        for resort, info in RESORT_STATIONS.items()
        if "IKON" in info.get("pass", [])
    }


FACTUAL_SPECS: dict[str, dict[str, Any]] = {
    "F01": {"valid_tops": {"Telluride"}, "requires_pass_filter": False},
    "F02": {"valid_tops": {"Loveland"}, "requires_pass_filter": False},
    "F03": {"valid_tops": {"Winter Park", "Eldora"}, "requires_pass_filter": True},
    "F04": {"valid_tops": {"Telluride"}, "requires_pass_filter": True},
    "F05": {"valid_tops": {"Loveland"}, "requires_pass_filter": True},
    "F06": {"valid_tops": {"Telluride"}, "requires_pass_filter": False},
    "F07": {"valid_tops": {"Loveland"}, "requires_pass_filter": False},
    "F08": {"valid_tops": {"Telluride"}, "requires_pass_filter": False},
    "F09": {"valid_tops": ikon_resorts(), "requires_pass_filter": True, "expects_no_snow": True},
    "F10": {"valid_tops": {"Loveland"}, "requires_pass_filter": False},
}


def answer_mentions_expected(answer: str, spec: dict[str, Any]) -> bool:
    answer_l = (answer or "").lower()
    if spec.get("expects_no_snow"):
        return "no resort" in answer_l or "no new snow" in answer_l
    valid_tops = spec["valid_tops"]
    return any(top.lower() in answer_l for top in valid_tops)


def score_factual_result(result: dict[str, Any]) -> dict[str, Any]:
    prompt_id = result["id"]
    spec = FACTUAL_SPECS[prompt_id]

    ranking = result.get("ranking") or []
    answer = result.get("answer", "")
    question = result.get("question", "")
    selected_passes = result.get("selected_passes") or ["All"]

    allowed_resorts = get_allowed_resorts(selected_passes, question)

    top_resort = ranking[0] if ranking else None
    top_resort_correct = top_resort in spec["valid_tops"] if top_resort else False
    pass_filter_respected = all(resort in allowed_resorts for resort in ranking)
    answer_ok = answer_mentions_expected(answer, spec)

    overall_correct = top_resort_correct and pass_filter_respected and answer_ok

    return {
        "id": prompt_id,
        "question": question,
        "top_resort": top_resort,
        "valid_top_resorts": sorted(spec["valid_tops"]),
        "top_resort_correct": top_resort_correct,
        "pass_filter_respected": pass_filter_respected,
        "answer_mentions_expected": answer_ok,
        "overall_correct": overall_correct,
    }


def summarize_scored(scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(scored_rows)
    return {
        "count": total,
        "top_resort_accuracy": sum(r["top_resort_correct"] for r in scored_rows) / total if total else 0.0,
        "pass_filter_accuracy": sum(r["pass_filter_respected"] for r in scored_rows) / total if total else 0.0,
        "answer_expected_accuracy": sum(r["answer_mentions_expected"] for r in scored_rows) / total if total else 0.0,
        "overall_accuracy": sum(r["overall_correct"] for r in scored_rows) / total if total else 0.0,
    }


def score_payload(payload: dict[str, Any], label: str) -> dict[str, Any]:
    factual_results = [r for r in payload.get("results", []) if str(r.get("id", "")).startswith("F")]
    scored_rows = [score_factual_result(r) for r in factual_results]
    return {
        "label": label,
        "meta": payload.get("meta", {}),
        "factual_rows": scored_rows,
        "summary": summarize_scored(scored_rows),
    }


def write_markdown_summary(summary_payload: dict[str, Any]) -> None:
    off = summary_payload["deterministic_off"]["summary"]
    on = summary_payload["deterministic_on"]["summary"]

    md = f"""# Evaluation Summary

## Scope
This summary compares the factual subset (F01-F10) of the Colorado Powracle benchmark in two modes:
- deterministic simple answers **off**
- deterministic simple answers **on**

## Input runs
- deterministic off: `{summary_payload["deterministic_off"]["source_path"]}`
- deterministic on: `{summary_payload["deterministic_on"]["source_path"]}`

## Factual results
### Deterministic off
- top-resort accuracy: **{off["top_resort_accuracy"]:.1%}**
- pass-filter accuracy: **{off["pass_filter_accuracy"]:.1%}**
- answer-mentions-expected accuracy: **{off["answer_expected_accuracy"]:.1%}**
- overall factual accuracy: **{off["overall_accuracy"]:.1%}**

### Deterministic on
- top-resort accuracy: **{on["top_resort_accuracy"]:.1%}**
- pass-filter accuracy: **{on["pass_filter_accuracy"]:.1%}**
- answer-mentions-expected accuracy: **{on["answer_expected_accuracy"]:.1%}**
- overall factual accuracy: **{on["overall_accuracy"]:.1%}**

## Takeaway
Deterministic mode is intended to improve a narrow set of simple factual live-data questions. In this benchmark, it should help the factual subset by making answers more controlled and more likely to respect pass-specific filtering.

## Notes
- This summary currently scores the factual subset only.
- Recommendation and explanatory prompts can be added later with a lightweight rubric.
"""
    SUMMARY_MD_PATH.write_text(md, encoding="utf-8")


def main() -> None:
    args = parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    off_path = Path(args.off) if args.off else choose_best_run("current_agent_outputs_deterministic_off_*.json")
    on_path = Path(args.on) if args.on else choose_best_run("current_agent_outputs_deterministic_on_*.json")

    off_payload = load_json(off_path)
    on_payload = load_json(on_path)

    off_scored = score_payload(off_payload, "deterministic_off")
    on_scored = score_payload(on_payload, "deterministic_on")

    summary_payload = {
        "deterministic_off": {
            **off_scored,
            "source_path": str(off_path),
        },
        "deterministic_on": {
            **on_scored,
            "source_path": str(on_path),
        },
    }

    with SUMMARY_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)

    write_markdown_summary(summary_payload)

    print(f"Wrote {SUMMARY_JSON_PATH}")
    print(f"Wrote {SUMMARY_MD_PATH}")
    print()
    print("Factual summary")
    print("---------------")
    for label in ("deterministic_off", "deterministic_on"):
        s = summary_payload[label]["summary"]
        print(label)
        print(f"  top_resort_accuracy      : {s['top_resort_accuracy']:.1%}")
        print(f"  pass_filter_accuracy     : {s['pass_filter_accuracy']:.1%}")
        print(f"  answer_expected_accuracy : {s['answer_expected_accuracy']:.1%}")
        print(f"  overall_accuracy         : {s['overall_accuracy']:.1%}")
        print()


if __name__ == "__main__":
    main()
