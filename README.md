# finlake — mini financial data lake with uv + medallion architecture

A small, complete, git-friendly project for learning modern data-engineering
fundamentals: **uv** for project management, **bronze/silver/gold** medallion
zones, **Hive-style partitioning** for painless future cloud migration, and a
structure built for **AI-assisted development** in an IDE.

## Quick start

```bash
# 1. Install uv (one time)
curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS/Linux
# powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows

# 2. Clone and set up — uv reads pyproject.toml + uv.lock and builds .venv
git clone <your-repo-url> && cd finlake
uv sync

# 3. Run the full pipeline: generate -> bronze -> silver -> gold -> report
uv run python -m finlake.pipeline all

# 4. Run tests
uv run pytest -v

# 5. Explore in Jupyter (VS Code: just open notebooks/ and pick the .venv kernel)
uv run jupyter lab
```

## What the pipeline does

```
generate (messy sample data: dupes, bad timestamps, nulls, outliers)
   │
   ▼
BRONZE  data/bronze/transactions/year=2026/month=01/part-0.parquet
        raw, as-is, immutable, + _ingested_at lineage column
   │
   ▼
SILVER  data/silver/transactions/year=.../month=.../part-0.parquet
        normalized strings, parsed timestamps, deduplicated,
        validated against config.yaml rules (rejects kept + counted),
        enriched (day_of_week, is_weekend, amount_bucket, is_refund)
   │
   ▼
GOLD    data/gold/transactions/*.parquet
        monthly_summary, top_merchants, category_breakdown,
        account_summary, health_metrics
   │
   ▼
REPORT  reports/financial_report.md
```

Each zone runs independently:

```bash
uv run python -m finlake.pipeline bronze
uv run python -m finlake.pipeline silver   # re-run after changing cleaning logic
uv run python -m finlake.pipeline gold
```

## Why Hive-style partitions (`year=2026/month=07/`)

This exact folder convention is natively understood by AWS Athena/Glue,
BigQuery external tables, Azure Synapse, Spark, DuckDB, and Trino. Migration
to cloud later is:

```bash
aws s3 sync data/ s3://my-lake/          # or: gsutil rsync -r data/ gs://my-lake/
```

…then point a query engine at the bucket. No code rewrite — only `lake.root`
in `config.yaml` changes conceptually.

## Security practices baked in

- `.gitignore` blocks `.env`, `*credentials*`, `service_account*.json`, keys
- Data zones are gitignored — the lake is *reproducible from code*, so it
  doesn't belong in git (also: real financial data must never be committed)
- Config (`config.yaml`) holds no secrets — only structure and rules
- If you later read real sources, put credentials in `.env`, load with
  `python-dotenv`, and never paste them into AI chats

## Learning path (suggested order)

1. **Run it end-to-end**, then read `reports/financial_report.md`
2. **Read `lake.py`** — the IO layer; understand `write_partitioned` and how
   partition columns are reconstructed on read
3. **Read `silver.py`** — pure-function cleaning steps chained with `.pipe()`
4. **Break something on purpose**: change a rule in `config.yaml`
   (e.g. remove "THB" from allowed currencies), re-run silver, watch the DQ
   summary change
5. **Read `tests/test_silver.py`** — then add one test yourself
6. **Exercises** (great to do with an AI assistant in your IDE):
   - Add a `weekly_summary` gold table
   - Add a validation rule: `account_id` must match `ACC\d{4}`
   - Add currency conversion to USD in silver (rates in config.yaml)
   - Add `day` as a third partition key and observe the folder explosion —
     then discuss with the AI why over-partitioning small data is an
     anti-pattern
   - Swap `format: csv` in config.yaml and confirm everything still runs
     (that's the abstraction paying off)

## Working with AI on this repo (the intended workflow)

- Open the repo in VS Code with Claude Code / Cursor
- Ask for changes at the *function* level: "add a cleaning step in silver.py
  that trims account_id whitespace, and a test for it"
- Always have the AI run `uv run pytest` after edits — the tests are the
  contract that keeps AI changes safe
- `uv add <package>` (not raw pip) so `pyproject.toml` + `uv.lock` stay in
  sync and the change shows up in your git diff
