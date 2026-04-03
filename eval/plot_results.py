"""
Generate simple evaluation figures from eval/results/scored_summary.json.

Usage:
    python -m eval.plot_results
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_JSON_PATH = ROOT / "eval" / "results" / "scored_summary.json"
FIGURES_DIR = ROOT / "eval" / "figures"


def load_summary() -> dict:
    with SUMMARY_JSON_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def plot_accuracy_bars(summary: dict) -> None:
    off = summary["deterministic_off"]["summary"]
    on = summary["deterministic_on"]["summary"]

    metrics = [
        ("Top resort", off["top_resort_accuracy"], on["top_resort_accuracy"]),
        ("Pass filter", off["pass_filter_accuracy"], on["pass_filter_accuracy"]),
        ("Answer text", off["answer_expected_accuracy"], on["answer_expected_accuracy"]),
        ("Overall", off["overall_accuracy"], on["overall_accuracy"]),
    ]

    labels = [m[0] for m in metrics]
    off_vals = [m[1] for m in metrics]
    on_vals = [m[2] for m in metrics]

    x = range(len(labels))
    width = 0.35

    plt.figure(figsize=(9, 5))
    plt.bar([i - width / 2 for i in x], off_vals, width=width, label="Deterministic off")
    plt.bar([i + width / 2 for i in x], on_vals, width=width, label="Deterministic on")
    plt.xticks(list(x), labels)
    plt.ylim(0, 1.05)
    plt.ylabel("Accuracy")
    plt.title("Factual benchmark accuracy by mode")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "factual_accuracy_comparison.png", dpi=200)
    plt.close()


def plot_per_prompt(summary: dict) -> None:
    off_rows = {row["id"]: row for row in summary["deterministic_off"]["factual_rows"]}
    on_rows = {row["id"]: row for row in summary["deterministic_on"]["factual_rows"]}

    prompt_ids = sorted(off_rows.keys())
    off_vals = [1.0 if off_rows[p]["overall_correct"] else 0.0 for p in prompt_ids]
    on_vals = [1.0 if on_rows[p]["overall_correct"] else 0.0 for p in prompt_ids]

    x = range(len(prompt_ids))
    width = 0.35

    plt.figure(figsize=(10, 5))
    plt.bar([i - width / 2 for i in x], off_vals, width=width, label="Deterministic off")
    plt.bar([i + width / 2 for i in x], on_vals, width=width, label="Deterministic on")
    plt.xticks(list(x), prompt_ids, rotation=45)
    plt.ylim(0, 1.05)
    plt.ylabel("Overall correct")
    plt.title("Per-prompt factual correctness")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "per_prompt_factual_correctness.png", dpi=200)
    plt.close()


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    summary = load_summary()
    plot_accuracy_bars(summary)
    plot_per_prompt(summary)
    print(f"Wrote figures to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
