"""Phase 1 / task 1.2 - ingest the 20-sheet workbook into the bronze layer.

Bronze keeps every cell as text exactly as written. We deliberately do NOT let pandas
convert placeholder text such as 'None' or 'N/A' into blanks, because whether a placeholder
means "missing" or "nothing to report" is a business decision (see DECISIONS D-008).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from hcls import config

LINEAGE_COLS = ["_source_sheet", "_row_num", "_ingested_at"]


def read_workbook(path: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Read every sheet as text. Only truly empty cells become NULL."""
    path = Path(path) if path else config.path("raw_workbook")
    frames = pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False, na_values=[""])
    out: dict[str, pd.DataFrame] = {}
    for name, df in frames.items():
        df = df.astype(object).where(df.notna(), None)
        out[name] = df
    return out


def add_lineage(name: str, df: pd.DataFrame, ingested_at: str) -> pd.DataFrame:
    df = df.copy()
    df["_source_sheet"] = name
    df["_row_num"] = range(2, len(df) + 2)  # Excel row number (header is row 1)
    df["_ingested_at"] = ingested_at
    return df


def ingest(path: Path | str | None = None, write: bool = True) -> dict[str, pd.DataFrame]:
    """Return {sheet: bronze frame}; optionally persist as parquet under outputs/bronze."""
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = read_workbook(path)
    bronze = {name: add_lineage(name, df, ts) for name, df in raw.items()}
    if write:
        out = config.outputs_dir("bronze")
        for name, df in bronze.items():
            df.to_parquet(out / f"{name}.parquet", index=False)
    return bronze


def data_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in LINEAGE_COLS and not c.startswith("_")]


def save_layer(layer: str, frames: dict[str, pd.DataFrame]) -> None:
    out = config.outputs_dir(layer)
    for name, df in frames.items():
        df.to_parquet(out / f"{name}.parquet", index=False)


def load_layer(layer: str) -> dict[str, pd.DataFrame]:
    """Read a persisted layer (bronze / silver). Returns {} when the layer has not been built yet."""
    folder = config.path("outputs") / layer
    frames: dict[str, pd.DataFrame] = {}
    if not folder.exists():
        return frames
    for f in sorted(folder.glob("*.parquet")):
        df = pd.read_parquet(f)
        frames[f.stem] = df.astype(object).where(df.notna(), None)
    return frames
