"""Tests for silver-zone cleaning logic.

Pattern to learn: transform functions are pure (DataFrame in -> DataFrame out),
so tests need tiny hand-written fixtures — no Sheets API, no files, no mocks.
This is exactly what makes AI-assisted refactoring safe: the AI edits
silver.py, then runs `uv run pytest` to prove it didn't break anything.
"""
import pandas as pd

from finlake.silver import deduplicate, normalize_strings, parse_timestamps, validate

RULES = {
    "allowed_status": ["completed", "pending", "failed", "refunded"],
    "allowed_currencies": ["USD", "THB"],
    "amount_min": -100000,
    "amount_max": 100000,
}


def test_normalize_strings_fixes_case_and_whitespace():
    df = pd.DataFrame({
        "merchant": [" Amazon "], "category": ["food"],
        "status": ["COMPLETED"], "currency": ["usd "],
    })
    out = normalize_strings(df)
    assert out.loc[0, "merchant"] == "Amazon"
    assert out.loc[0, "status"] == "completed"
    assert out.loc[0, "currency"] == "USD"


def test_deduplicate_keeps_first():
    df = pd.DataFrame({"transaction_id": ["A", "A", "B"], "amount": [1, 2, 3]})
    out = deduplicate(df)
    assert len(out) == 2
    assert out[out["transaction_id"] == "A"]["amount"].iloc[0] == 1


def test_parse_timestamps_handles_mixed_formats():
    df = pd.DataFrame({"timestamp": ["2026-03-01T10:00:00", "15/03/2026 14:30", "garbage"]})
    out = parse_timestamps(df)
    assert out["timestamp"].notna().sum() == 2
    assert out["timestamp"].isna().sum() == 1


def test_validate_rejects_bad_rows_with_reasons():
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-01-01", "2026-01-02", None]),
        "status": ["completed", "hacked", "completed"],
        "currency": ["USD", "USD", "USD"],
        "amount": [10.0, 20.0, 30.0],
    })
    valid, rejected = validate(df, RULES)
    assert len(valid) == 1
    assert len(rejected) == 2
    assert "invalid_status" in rejected["reject_reason"].iloc[0]


def test_validate_amount_bounds():
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-01-01", "2026-01-01"]),
        "status": ["completed", "completed"],
        "currency": ["USD", "USD"],
        "amount": [50.0, 9_999_999.0],
    })
    valid, rejected = validate(df, RULES)
    assert len(valid) == 1
    assert "amount_out_of_range" in rejected["reject_reason"].iloc[0]
