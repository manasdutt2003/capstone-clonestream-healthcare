from __future__ import annotations

import pandas as pd
import pytest

from hcls import config, ingest, standardise
from hcls.dq import runner


@pytest.fixture(scope="session")
def bronze():
    return ingest.ingest(write=False)


@pytest.fixture(scope="session")
def cleaned(bronze):
    return standardise.standardise(bronze)  # (silver, changes)


@pytest.fixture(scope="session")
def raw_results(bronze):
    res, tl, fails = runner.run_rules(bronze)
    return res.set_index("rule_id"), tl, fails


@pytest.fixture(scope="session")
def clean_results(cleaned):
    res, _, _ = runner.run_rules(cleaned[0])
    return res.set_index("rule_id")


@pytest.fixture
def tmp_outputs(tmp_path, monkeypatch):
    """Redirect every output path (parquet, gold, workbook, docs) into a temp folder."""
    cfg = config.load_config()
    monkeypatch.setitem(cfg["paths"], "outputs", str(tmp_path / "outputs"))
    monkeypatch.setitem(cfg["paths"], "clean_workbook", str(tmp_path / "clean" / "HCLS_cleaned.xlsx"))
    monkeypatch.setattr(config, "docs_dir", lambda *parts: _mk(tmp_path.joinpath("docs", *parts)))
    return tmp_path


def _mk(p):
    p.mkdir(parents=True, exist_ok=True)
    return p


def frame(rows: list[dict], columns: list[str] | None = None) -> pd.DataFrame:
    """Tiny text-only table with the Excel row number column the engine expects."""
    df = pd.DataFrame(rows, columns=columns)
    df = df.astype(object).where(df.notna(), None)
    df["_row_num"] = range(2, len(df) + 2)
    return df
