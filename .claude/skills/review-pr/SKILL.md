---
name: review-pr
description: Review ALL open pull requests against the project PR template, fix their bodies, post detailed comments, and update the PR template itself if new checks are discovered.
argument-hint: "[optional: pr-number] [--fix | --discuss]"
allowed-tools: Bash, Read, Glob, Grep, Edit, Write, AskUserQuestion
---

# PR Template Reviewer

Review open pull requests, enforce template compliance by **reading the actual code diff**, post detailed audit comments, and keep the PR template up to date with any new rules discovered during review.

> **Critical rule:** Do NOT simply check whether a checkbox is ticked. For every checklist item, verify it yourself by reading the diff or the changed files. A checked box that fails code verification is a blocking issue.

## Steps

### 1. Load the template
Read `.github/pull_request_template.md` in full before doing anything else.

### 2. Get the full PR list
- If `$ARGUMENTS` is a specific PR number, review only that PR.
- Otherwise: `gh pr list --state open --json number,title,headRefName`
- **Review every PR in the list — do not skip any.**
- Keep a running log of every new rule or check category discovered across all PRs.

### 3. For each PR — gather facts
```bash
gh pr view <NUMBER> --json number,title,body,headRefName
gh pr diff <NUMBER> --name-only      # list of changed files
gh pr diff <NUMBER>                  # full diff — read this carefully
```

Determine which sections apply based on changed files:
| Changed path | Applicable section |
|---|---|
| `tools/` | If you added or modified a tool |
| `ingestion/` | If you added or changed ingestion |
| `db/` | If you changed the DuckDB schema or views |
| `agent/` | If you changed the agent |
| `app.py` | If you changed the UI |
| New external service / API key | If you added a new API or external service |
| New infrastructure (Docker, Postgres, etc.) | New infrastructure checklist |

### 4. For each PR — verify every checklist item from the code

**Do not trust checked boxes.** For each item below, run the verification command and record pass/fail:

#### Always section
| Item | How to verify |
|---|---|
| App starts without errors | In `--fix` mode: check out the PR branch, run `conda activate powracle && timeout 15 streamlit run app.py &` then check if the process started without errors and kill it. In `--discuss` mode: flag as "author must confirm". |
| Tested 2 canonical questions | In `--fix` mode: check out the PR branch, run 2 canonical questions from CLAUDE.md through the agent via a Python one-liner (`agent.invoke()`). Pick questions relevant to the PR's changes plus one general question. Record the tool calls and final answer. In `--discuss` mode: flag as "author must confirm". |
| No `.env`, `data/`, `*.duckdb`, `*.parquet` staged | Check `gh pr diff <N> --name-only` for these patterns |
| No `.claude/settings.local.json` staged | Check `gh pr diff <N> --name-only` for `settings.local.json` |
| No runtime artifact files staged | Check `gh pr diff <N> --name-only` for `eval/results/`, timestamped JSONs, output dumps |
| No relative paths introduced | `gh pr diff <N>` — grep for `open(`, `Path("`, `os.path.join("` and verify they use `Path(__file__).resolve()` |
| No system Python | `gh pr diff <N>` — grep for `/usr/bin/python`, `python3` shebang without conda path |

#### Documentation section
| Item | How to verify |
|---|---|
| `CLAUDE.md` updated | Check if `CLAUDE.md` is in the changed files list; if new features were added, read the diff to confirm relevant sections were updated |
| `AGENTS.md` updated | Same as CLAUDE.md — check it's in the diff if applicable |
| Subdirectory `CLAUDE.md` updated | Check changed files for `tools/CLAUDE.md`, `ingestion/CLAUDE.md`, etc. |
| `CONTEXT_MIN.md` updated | Check if new critical rules were introduced and whether `CONTEXT_MIN.md` is in the diff |
| `ONBOARDING.md` updated | If setup steps changed, verify `ONBOARDING.md` is in the diff |
| `README.md` updated | If user-facing features changed, verify `README.md` is in the diff |

#### Tools section (if `tools/` changed)
| Item | How to verify |
|---|---|
| Tool accepts single `str`, returns non-empty `str` | Read the function signature and return statements in the diff |
| Tool registered in `agent/agent.py` | Check if `agent/agent.py` is in the diff and the tool name appears in the tools list |
| Knowledge block in `agent/prompts.py` | Check if `agent/prompts.py` is in the diff and a new block was added |
| Tool table updated in `CLAUDE.md` and `AGENTS.md` | Grep for the tool name in the `CLAUDE.md`/`AGENTS.md` diff |
| `tools/CLAUDE.md` updated | Check it's in the changed files |

#### API / external service section
| Item | How to verify |
|---|---|
| Key never committed | Grep the diff for anything resembling an API key (long alphanumeric strings, `sk-`, `Bearer `) |
| Key documented in context files | Grep the `CLAUDE.md`/`AGENTS.md`/`README.md` diffs for the key name |
| Graceful fallback | Read the tool/service code in the diff — look for try/except around external calls and a meaningful fallback return value |

#### Infrastructure section (if Docker, Postgres, new DB engine added)
| Item | How to verify |
|---|---|
| Setup file documented | Check for `docker-compose.yml`, `schema.sql`, migration scripts in the diff |
| `ONBOARDING.md` updated | Verify it's in the diff with the new setup steps |
| `CLAUDE.md` / `AGENTS.md` updated | Verify they mention the new dependency |
| Graceful fallback | Read the DB connection code — look for try/except and fallback behavior |

#### DB section (if `db/` changed)
| Item | How to verify |
|---|---|
| `db/setup.py` updated | Check it's in the changed files |
| `db/CLAUDE.md` updated | Check it's in the changed files |
| Rebuild instructions in PR | Read the PR body — confirm the DuckDB rebuild section is filled in |

#### Agent section (if `agent/` changed)
| Item | How to verify |
|---|---|
| `agent/CLAUDE.md` updated | Check it's in the changed files if `build_agent()` or `SYSTEM_PROMPT` changed |

#### UI section (if `app.py` changed)
| Item | How to verify |
|---|---|
| No layout errors | Cannot verify at review time — flag as "author must confirm" |
| `CLAUDE.md` UI section updated | Grep `CLAUDE.md` diff for the new UI feature name |
| `AGENTS.md` updated | Same check |

#### Design principles
| Item | How to verify |
|---|---|
| No existing modules rewritten | Read the diff — look for large deletions in existing files vs. new files added |
| Absolute paths preserved | Grep the diff for `Path(__file__).resolve().parent.parent` in any new path construction |
| `.env` loading uses explicit path | Grep the diff for `load_dotenv()` — must have explicit `dotenv_path=` argument |
| No duplicate logic | Read the diff — look for copy-pasted helper functions that already exist |
| Tool failures return strings, never raise | Read tool functions in diff — look for bare `raise` or unhandled exceptions leaking out |
| LangChain version unchanged | Check if `requirements.txt` or `environment.yml` is in the diff and `langchain` version changed |

### 5. For each PR — draft the updated body
- Keep the author's original description in "What this PR does" (improve clarity if vague).
- Check the correct "Type of change" box(es) inferred from changed files.
- For every checklist section:
  - Mark "N/A" if the section clearly does not apply (verified from diff).
  - Check items that **passed code verification**.
  - Leave unchecked (with an inline note) items that failed or could not be verified at review time (runtime tests, etc.).
- Flag any committed artifacts or sensitive files at the top of the body with a `> **Note for reviewer:**` block.

### 6. For each PR — update the body and post a detailed comment
```bash
gh pr edit <NUMBER> --body "..."
gh pr comment <NUMBER> --body "..."
```

The comment must include:
- For each checklist item: **how it was verified** (command run or file read) and **pass/fail result**
- For each failure: what was found, why it matters, what needs to change before merge
- For runtime items that cannot be code-verified: explicitly flag them as "author must confirm"
- A final action list for the author

### 7. Checkpoint — ask the user before fixing

After posting the review comment, if there are **any fixable blocking issues** (missing doc updates, missing files, code issues — anything you can fix by editing files), behavior depends on the mode flag in `$ARGUMENTS`:

**Parse the mode flag from `$ARGUMENTS`:**
- `--fix` → auto-fix all blocking issues immediately (skip to Step 8)
- `--discuss` → present the issues and wait for the user to approve before fixing (default)
- No flag → same as `--discuss`

**In `--discuss` mode (default)**, present the issues and wait:

```
Found N blocking issues I can fix:
1. [brief description of issue]
2. [brief description of issue]
...

Want to discuss these, or should I go ahead and fix? (use --fix next time to skip this step)
```

**Wait for the user's response before proceeding.** Do NOT fix issues without explicit approval. The user may want to push back on whether something is truly blocking, adjust the approach, or handle it themselves.

- If the user explicitly says to fix (e.g. "fix", "go ahead", "yes") → proceed to Step 8.
- If the user wants to discuss → answer their questions, and only proceed to Step 8 when they explicitly say to go ahead.
- If the user says to skip → skip Step 8 entirely and go to Step 9.

**In `--fix` mode**, skip the checkpoint and proceed directly to Step 8.

### 8. Fix blocking issues and run runtime checks

**Check out the PR branch first**: `gh pr checkout <NUMBER>`

#### 8a. Fix code/doc issues
For each fixable issue:
1. **Make the code/doc changes** using Edit or Write tools
2. **Commit with a clear message** explaining what was fixed and why
3. **Push** to the PR branch

#### 8b. Run runtime verification (always in `--fix` mode)
These checks were previously "author must confirm" but in `--fix` mode you run them yourself:

**App startup test:**
```bash
cd /Users/chli4608/Repositories/colorado_powder_oracle
/opt/anaconda3/envs/powracle/bin/python -c "
import subprocess, time, signal, sys
proc = subprocess.Popen(
    ['/opt/anaconda3/envs/powracle/bin/streamlit', 'run', 'app.py', '--server.headless=true'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)
time.sleep(10)
proc.send_signal(signal.SIGTERM)
stdout, stderr = proc.communicate(timeout=5)
output = stdout + stderr
if 'Error' in output or proc.returncode not in (0, -15, None):
    print('FAIL: App crashed on startup')
    print(output[-500:])
    sys.exit(1)
else:
    print('PASS: App started without errors')
"
```

**Canonical questions test:**
Run 2 questions through the agent — pick one relevant to the PR's changes, one general:
```bash
PYTHONPATH=/Users/chli4608/Repositories/colorado_powder_oracle \
  /opt/anaconda3/envs/powracle/bin/python -c "
from agent.agent import build_agent
agent = build_agent(verbose=True)
# Q1: relevant to this PR
result = agent.invoke({'messages': [('human', '<question>')]})
print('Q1 ANSWER:', result['messages'][-1].content[:300])
# Q2: general sanity check
result = agent.invoke({'messages': [('human', '<question>')]})
print('Q2 ANSWER:', result['messages'][-1].content[:300])
"
```
Replace `<question>` with actual canonical questions from CLAUDE.md. Record which tool was called and whether the answer is reasonable.

#### 8c. Post follow-up comment
Post a comment on the PR summarizing:
- Which files were changed and what each change does
- Runtime test results (app startup: pass/fail, each canonical question: tool called + answer summary)
- Which checklist items are now resolved
- Any remaining items (there should be none in `--fix` mode)

After fixing, update the PR body to check off the newly-resolved items.

### 9. After all PRs — update the PR template if needed
Review your running log of new checks discovered. For any check that:
- Was missing from the template and needed to be applied to one or more PRs, OR
- Represents a recurring risk not currently covered

→ Add it to `.github/pull_request_template.md` in the most relevant section.

Then post a summary comment listing every rule added and why.

**Current known rules to ensure are in the template:**
- No `.env`, `data/`, `*.duckdb`, `*.parquet` staged (already present)
- No `.claude/settings.local.json` committed
- No runtime artifact files committed (`eval/results/`, timestamped JSONs, output dumps)
- New infrastructure (Docker, Postgres, etc.) must be documented in `ONBOARDING.md`
- New external services must implement graceful fallback when unavailable
- `requirements_*.txt` additions must be reflected in `CLAUDE.md` / `ONBOARDING.md`

## Rules: what constitutes a template violation
- A checked box that fails code verification → blocking violation
- Any unchecked checkbox with no "N/A" annotation → violation
- "What this PR does" is a placeholder or too vague → violation
- A section-specific checklist is absent when it applies → violation
- A file that should never be committed is staged → violation, flag prominently
- A new infrastructure dependency with no doc update → violation
