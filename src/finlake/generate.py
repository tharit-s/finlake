"""Generate realistic *messy* financial transaction data.

The mess is intentional — silver-zone cleaning needs something to clean:
- duplicate transaction_ids
- inconsistent currency casing ("usd", "USD ")
- nulls in merchant/category
- impossible amounts (huge outliers)
- mixed timestamp formats
- whitespace in string fields
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

import pandas as pd

MERCHANTS = ["Amazon", "Starbucks", "Grab", "Shopee", "Netflix", "7-Eleven",
             "Apple", "Lazada", "AirAsia", "Tesco Lotus", None]
CATEGORIES = ["shopping", "food", "transport", "entertainment",
              "subscription", "travel", "groceries", None]
CURRENCIES = ["USD", "usd", "EUR", "GBP", "THB", "THB "]
STATUSES = ["completed", "completed", "completed", "pending", "failed", "refunded", "COMPLETED"]


def generate_transactions(n: int = 5000, seed: int = 42,
                          start: str = "2026-01-01", months: int = 6) -> pd.DataFrame:
    rng = random.Random(seed)
    start_dt = datetime.fromisoformat(start)
    end_dt = start_dt + timedelta(days=months * 30)
    span_seconds = int((end_dt - start_dt).total_seconds())

    rows = []
    for i in range(n):
        ts = start_dt + timedelta(seconds=rng.randint(0, span_seconds))
        # mixed timestamp formats — a classic real-world mess
        ts_str = ts.isoformat() if rng.random() < 0.8 else ts.strftime("%d/%m/%Y %H:%M")
        amount = round(rng.lognormvariate(3.5, 1.2), 2)
        if rng.random() < 0.005:            # rare absurd outlier
            amount = round(amount * 10000, 2)
        if rng.random() < 0.03:             # refund-style negative
            amount = -amount
        rows.append({
            "transaction_id": f"TXN{i:07d}",
            "timestamp": ts_str,
            "account_id": f"ACC{rng.randint(1, 200):04d}",
            "merchant": rng.choice(MERCHANTS),
            "category": rng.choice(CATEGORIES),
            "amount": amount,
            "currency": rng.choice(CURRENCIES),
            "status": rng.choice(STATUSES),
        })

    df = pd.DataFrame(rows)
    # inject exact duplicates (~1%)
    dupes = df.sample(frac=0.01, random_state=seed)
    return pd.concat([df, dupes], ignore_index=True).sample(frac=1, random_state=seed)
