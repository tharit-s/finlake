# finlake — project context for Claude Code

## What this is
A learning project: financial-transactions data lake using medallion
architecture (bronze/silver/gold), managed with `uv`, designed for eventual
migration to a cloud data lake and orchestration with Airflow.

## Stack decisions (don't change without discussion)
- Package manager: **uv** (`pyproject.toml` + `uv.lock`) — not pip/venv/poetry
- Storage format: **Parquet**, Hive-style partitions (`year=YYYY/month=MM/`)
  — config.yaml has a `csv` fallback for restricted environments
- Data source: `src/finlake/generate.py` produces synthetic messy data today;
  this will later be swapped for a Google Sheets reader — nothing downstream
  of "a DataFrame arrives" should need to change when that happens
- Orchestration target: Airflow later — each zone already runs independently
  via `python -m finlake.pipeline {bronze|silver|gold}`, communicates only
  through files on disk, and is idempotent (safe to rerun). A draft DAG
  design exists in conversation history; ask before generating dags/ files.

## Commands
```bash
uv sync                                  # install/sync deps
uv run python -m finlake.pipeline all    # generate -> bronze -> silver -> gold -> report
uv run python -m finlake.pipeline silver # rerun one zone only
uv run pytest -v                         # run tests — ALWAYS run after edits
uv run ruff check src/                   # lint
```

## Non-negotiable rules for this project
1. Every transform function in `silver.py` / `gold.py` must be a **pure
   function** (DataFrame in, DataFrame out) — no I/O inside them. IO lives
   only in `lake.py`.
2. Rejected/invalid rows are **never silently dropped** — they get a reason
   and get written to `data/silver/_quality/rejected_rows.parquet`.
3. Every new transform function needs a matching test in `tests/`.
4. Use `uv add <package>` to add dependencies — never raw `pip install` —
   so `pyproject.toml` and `uv.lock` stay in sync.
5. After any code change, run `uv run pytest` before considering the change
   done. If a test fails, fix it or explain why the test itself is wrong.
6. Never commit `data/`, `.venv/`, `.env`, or any `*credentials*`/`*.json`
   secrets — `.gitignore` already blocks these, keep it that way.

## Current status / where we left off
- [x] Bronze, silver, gold zones implemented and verified end-to-end
- [x] 5 tests passing in tests/test_silver.py
- [x] Markdown report generation working
- [ ] Not yet done: weekly_summary gold table (exercise)
- [ ] Not yet done: account_id format validation rule
- [ ] Not yet done: currency conversion in silver
- [ ] Not yet done: real Google Sheets source (currently synthetic data)
- [ ] Not yet done: Airflow dags/ folder (design discussed, not built)

## Style
Keep functions small, docstrings short and purpose-first (see existing files
for tone). Prefer explicit code over clever one-liners — this repo is a
teaching artifact as much as a working pipeline.
