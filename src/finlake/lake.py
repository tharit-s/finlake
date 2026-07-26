"""Lake IO layer: zone paths, Hive-style partitioned writes, format abstraction.

Design goals:
- One place that knows *where* data lives and *how* it's stored.
- Hive-style partition folders (year=YYYY/month=MM) so the same layout works
  locally today and on S3/GCS/ADLS + Athena/BigQuery/Synapse tomorrow.
- Everything else (bronze/silver/gold logic) stays pure and testable.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(path: Path | str = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def zone_path(cfg: dict, zone: str, dataset: str) -> Path:
    root = Path(cfg["lake"]["root"])
    return root / cfg["lake"]["zones"][zone] / dataset


def _write_one(df: pd.DataFrame, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "parquet":
        df.to_parquet(path, index=False)
    elif fmt == "csv":
        df.to_csv(path, index=False)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def _read_one(path: Path, fmt: str) -> pd.DataFrame:
    if fmt == "parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def write_partitioned(df: pd.DataFrame, cfg: dict, zone: str, dataset: str,
                      overwrite_partitions: bool = True) -> list[Path]:
    """Write a DataFrame as Hive-style partitions: <zone>/<dataset>/year=YYYY/month=MM/part-0.<fmt>

    overwrite_partitions=True makes reruns idempotent: each partition present in
    `df` is fully replaced, partitions not present are left untouched.
    """
    fmt = cfg["lake"]["format"]
    keys = cfg["partitioning"]["keys"]
    base = zone_path(cfg, zone, dataset)

    missing = [k for k in keys if k not in df.columns]
    if missing:
        raise ValueError(f"Partition key(s) missing from DataFrame: {missing}")

    written: list[Path] = []
    for part_values, part_df in df.groupby(keys, sort=True):
        if not isinstance(part_values, tuple):
            part_values = (part_values,)
        part_dir = base
        for key, value in zip(keys, part_values):
            if key == "month":
                value = f"{int(value):02d}"
            part_dir = part_dir / f"{key}={value}"
        if overwrite_partitions and part_dir.exists():
            shutil.rmtree(part_dir)
        out = part_dir / f"part-0.{fmt}"
        _write_one(part_df.drop(columns=keys), out, fmt)
        written.append(out)
    return written


def read_partitioned(cfg: dict, zone: str, dataset: str) -> pd.DataFrame:
    """Read all partitions of a dataset back into one DataFrame,
    reconstructing partition columns from the folder names."""
    fmt = cfg["lake"]["format"]
    base = zone_path(cfg, zone, dataset)
    files = sorted(base.rglob(f"part-*.{fmt}"))
    if not files:
        raise FileNotFoundError(f"No {fmt} files under {base} — did the upstream zone run?")

    frames = []
    for f in files:
        df = _read_one(f, fmt)
        # Recover partition values from path segments like "year=2026"
        for segment in f.relative_to(base).parts[:-1]:
            key, _, value = segment.partition("=")
            df[key] = int(value) if value.isdigit() else value
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def write_table(df: pd.DataFrame, cfg: dict, zone: str, dataset: str, name: str) -> Path:
    """Write a small, non-partitioned table (typical for gold aggregates)."""
    fmt = cfg["lake"]["format"]
    out = zone_path(cfg, zone, dataset) / f"{name}.{fmt}"
    _write_one(df, out, fmt)
    return out
