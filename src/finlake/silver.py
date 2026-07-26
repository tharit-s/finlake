"""Silver zone: cleaned, validated, typed, deduplicated, enriched.

This is where data *quality* is enforced. Every rule is a small pure function,
and every row we reject is counted — a data-quality (DQ) summary is a
first-class output, not an afterthought.
"""
from __future__ import annotations

import pandas as pd

from .lake import read_partitioned, write_partitioned

DATASET = "transactions"


# ---------- cleaning steps (pure functions — easy to test, easy for AI to improve) ----------

def normalize_strings(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["merchant", "category", "status", "currency"]:
        out[col] = out[col].astype("string").str.strip()
    out["status"] = out["status"].str.lower()
    out["currency"] = out["currency"].str.upper()
    return out


def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce",
                                      format="mixed", dayfirst=True)
    return out


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset=["transaction_id"], keep="first")


def fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["merchant"] = out["merchant"].fillna("UNKNOWN")
    out["category"] = out["category"].fillna("uncategorized")
    return out


def validate(df: pd.DataFrame, rules: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split rows into (valid, rejected) with a reject reason. Nothing is
    silently dropped — rejected rows are kept for inspection."""
    reasons = pd.Series("", index=df.index, dtype="string")

    bad_ts = df["timestamp"].isna()
    reasons[bad_ts] += "unparseable_timestamp;"

    bad_status = ~df["status"].isin(rules["allowed_status"])
    reasons[bad_status] += "invalid_status;"

    bad_ccy = ~df["currency"].isin(rules["allowed_currencies"])
    reasons[bad_ccy] += "invalid_currency;"

    bad_amt = (df["amount"] < rules["amount_min"]) | (df["amount"] > rules["amount_max"])
    reasons[bad_amt] += "amount_out_of_range;"

    rejected = df[reasons != ""].copy()
    rejected["reject_reason"] = reasons[reasons != ""]
    valid = df[reasons == ""].copy()
    return valid, rejected


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns analysts actually use."""
    out = df.copy()
    out["year"] = out["timestamp"].dt.year
    out["month"] = out["timestamp"].dt.month
    out["day_of_week"] = out["timestamp"].dt.day_name()
    out["is_weekend"] = out["timestamp"].dt.dayofweek >= 5
    out["amount_abs"] = out["amount"].abs()
    out["is_refund"] = (out["amount"] < 0) | (out["status"] == "refunded")
    out["amount_bucket"] = pd.cut(
        out["amount_abs"],
        bins=[0, 10, 50, 200, 1000, float("inf")],
        labels=["micro", "small", "medium", "large", "huge"],
    )
    return out


# ---------- orchestration ----------

def run(cfg: dict) -> pd.DataFrame:
    bronze_df = read_partitioned(cfg, "bronze", DATASET)
    n_in = len(bronze_df)

    df = (bronze_df
          .drop(columns=["_ingested_at", "year", "month"], errors="ignore")
          .pipe(normalize_strings)
          .pipe(parse_timestamps)
          .pipe(deduplicate)
          .pipe(fill_missing))

    valid, rejected = validate(df, cfg["quality"])
    silver_df = enrich(valid)

    write_partitioned(silver_df, cfg, "silver", DATASET)

    dq = pd.DataFrame([{
        "rows_in_bronze": n_in,
        "duplicates_removed": n_in - len(df),
        "rows_rejected": len(rejected),
        "rows_in_silver": len(silver_df),
        "pct_passed": round(100 * len(silver_df) / n_in, 2),
    }])
    print("[silver] data-quality summary:")
    print(dq.to_string(index=False))
    if len(rejected):
        print("[silver] top reject reasons:")
        print(rejected["reject_reason"].value_counts().head().to_string())

    from .lake import write_table
    write_table(dq, cfg, "silver", "_quality", "dq_summary")
    if len(rejected):
        write_table(rejected, cfg, "silver", "_quality", "rejected_rows")
    return silver_df
