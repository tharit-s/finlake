"""Bronze zone: ingest raw data AS-IS.

Rules of bronze:
- No cleaning, no type fixing, no dedup. Store what arrived.
- Add ingestion metadata (_ingested_at) for lineage/debugging.
- Partition by event date so downstream reads can prune.

Why keep the mess? If silver logic has a bug, you re-run silver from bronze
without re-fetching the source. Bronze is your replayable history.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .lake import write_partitioned

DATASET = "transactions"


def _derive_partitions(df: pd.DataFrame) -> pd.DataFrame:
    """Best-effort event-date partitions. Bronze tolerates bad timestamps —
    unparseable ones land in year=1970/month=01 instead of being dropped."""
    ts = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed", dayfirst=True)
    fallback = pd.Timestamp("1970-01-01")
    ts = ts.fillna(fallback)
    out = df.copy()
    out["year"] = ts.dt.year
    out["month"] = ts.dt.month
    return out


def ingest(raw_df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = _derive_partitions(raw_df)
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    paths = write_partitioned(df, cfg, "bronze", DATASET)
    print(f"[bronze] wrote {len(df):,} rows into {len(paths)} partitions")
    return df
