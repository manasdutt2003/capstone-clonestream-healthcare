"""Small parsing helpers shared by the remediation modules (all inputs are cleaned text columns)."""

from __future__ import annotations

import pandas as pd


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype("string").str.slice(0, 10), errors="coerce")


def blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype("string").str.strip() == "")
