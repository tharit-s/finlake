"""Pipeline entrypoint.

Usage (with uv):
    uv run python -m finlake.pipeline all        # generate -> bronze -> silver -> gold
    uv run python -m finlake.pipeline generate   # just create sample raw data
    uv run python -m finlake.pipeline bronze
    uv run python -m finlake.pipeline silver
    uv run python -m finlake.pipeline gold

Each zone can be run independently — that's the point of medallion layers:
fix silver logic, re-run silver+gold, never re-ingest bronze.
"""
from __future__ import annotations

import sys

from . import bronze, gold, silver
from .generate import generate_transactions
from .lake import load_config


def main() -> None:
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    cfg = load_config()

    if step in ("generate", "bronze", "all"):
        raw = generate_transactions(n=5000)
        print(f"[generate] {len(raw):,} raw rows (with intentional mess)")
        if step == "generate":
            raw.to_csv("data/_landing_sample.csv", index=False)
            return
        bronze.ingest(raw, cfg)

    if step in ("silver", "all"):
        silver.run(cfg)

    if step in ("gold", "all"):
        gold.run(cfg)


if __name__ == "__main__":
    main()
