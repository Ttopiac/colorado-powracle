# Evaluation Runner

This folder contains the first-pass benchmark setup for Colorado Powracle.

## Files

- `deterministic_answers_eval.csv' — benchmark prompt dataset
- `run_agent_eval.py` — script for running the current local system on the prompt set
- `results/` — generated output files (local artifacts)

## Prompt set

The prompt dataset currently includes three categories:

- **factual** — simple objective questions about current conditions
- **recommendation** — constrained recommendation questions
- **explanatory** — historical / comparative / descriptive questions

Each prompt row includes:
- `id`
- `category`
- `question`
- `selected_passes`
- `start_city`
- `expected_type`
- `notes`

## How to run

From the project root:

```bash
python -m eval.run_agent_eval
python -m eval.run_agent_eval --use-deterministic-simple-answers
```

Optional smoke test:

```bash
python -m eval.run_agent_eval --limit 5
```

## Output

The script writes JSON files into `eval/results/` with metadata and per-prompt outputs.

Typical output structure:
- `meta`
- `results`
- `errors`

## Initial observations

Using the current prompt set:

- the benchmark runner successfully executes the prompt dataset and saves structured outputs
- deterministic mode is useful on the factual subset because it produces cleaner, more controlled answers for simple live-data ranking questions
- recommendation and explanatory prompts still flow through the regular agent path

## Notes

- `eval/results/` contains generated artifacts and can be kept local while the evaluation pipeline is still evolving
- if collaborators merge changes into `main`, do a quick sync with `main/origin` before starting new work or rerunning benchmarks
