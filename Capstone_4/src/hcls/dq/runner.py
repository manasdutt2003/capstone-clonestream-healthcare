"""Execute rules against a set of tables using DuckDB (Phase 1, task 1.4)."""

from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from hcls import config
from hcls.dq.rules import META_TABLES, PYTHON_RULES, Rule, build_rules
from hcls.ingest import data_columns

MACROS = """
CREATE OR REPLACE MACRO as_of() AS CAST('{as_of}' AS DATE);
CREATE OR REPLACE MACRO missing(x) AS (x IS NULL OR lower(trim(x)) IN ('', 'n/a', 'na', '#n/a', 'null', 'unknown', 'nan'));
CREATE OR REPLACE MACRO yr(x) AS CASE WHEN regexp_matches(x, '^[0-9]{{4}}-') THEN substr(x, 1, 4) END;
CREATE OR REPLACE MACRO d(x) AS CASE WHEN regexp_matches(x, '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}') THEN TRY_CAST(substr(x, 1, 10) AS DATE) END;
CREATE OR REPLACE MACRO ts(x) AS CASE WHEN regexp_matches(x, '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}[T ][0-9]{{2}}:[0-9]{{2}}') THEN TRY_CAST(x AS TIMESTAMP) END;
CREATE OR REPLACE MACRO n(x) AS TRY_CAST(x AS DOUBLE);
CREATE OR REPLACE MACRO i(x) AS TRY_CAST(x AS BIGINT);
"""


def connect(frames: dict[str, pd.DataFrame]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(MACROS.format(as_of=config.as_of_date().isoformat()))
    for name, df in frames.items():
        df = df.astype(object).where(df.notna(), None)
        con.register(name, df)
    return con


def table_columns(frames: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    return {t: data_columns(df) for t, df in frames.items() if t not in META_TABLES}


def _row_level(rule: Rule, con, frames) -> pd.DataFrame:
    if rule.python_fn:
        return PYTHON_RULES[rule.python_fn](frames)
    return con.execute(rule.sql).df()


def run_rules(
    frames: dict[str, pd.DataFrame], rules: list[Rule] | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run all rules. Returns (results, timeline, failures).

    results  : one row per rule with rows_checked / rows_failed
    timeline : rows_checked / rows_failed per rule per year
    failures : (rule_id, table, row_num) for every failing record
    """
    rules = rules or build_rules(table_columns(frames))
    con = connect(frames)
    res, tl, fails = [], [], []
    for rule in rules:
        if rule.table not in frames:
            continue
        df = _row_level(rule, con, frames)
        df["failed"] = df["failed"].astype(bool)
        df["in_scope"] = df["in_scope"].astype(bool)
        scoped = df[df["in_scope"]]
        res.append(
            {
                "rule_id": rule.id,
                "table": rule.table,
                "column": rule.column,
                "rows_checked": int(len(scoped)),
                "rows_failed": int(scoped["failed"].sum()),
            }
        )
        if rule.table in frames:
            by_year = (
                scoped.assign(yr=scoped["yr"].where(scoped["yr"].notna(), None))
                .groupby("yr", dropna=True)["failed"]
                .agg(["size", "sum"])
            )
            for yr, row in by_year.iterrows():
                tl.append(
                    {
                        "rule_id": rule.id,
                        "table": rule.table,
                        "year": int(yr),
                        "rows_checked": int(row["size"]),
                        "rows_failed": int(row["sum"]),
                    }
                )
        bad = scoped[scoped["failed"]]
        if len(bad):
            fails.append(
                pd.DataFrame(
                    {"rule_id": rule.id, "table": rule.table, "row_num": bad["row_num"].astype(int).values}
                )
            )
    con.close()
    results = pd.DataFrame(res)
    meta = pd.DataFrame(
        [
            {
                "rule_id": r.id,
                "name": r.name,
                "check_type": r.check_type,
                "severity": r.severity,
                "stakeholder": r.stakeholder,
                "impact_statement": r.impact,
                "source": r.source,
            }
            for r in rules
        ]
    )
    results = results.merge(meta, on="rule_id", how="left")
    timeline = pd.DataFrame(tl, columns=["rule_id", "table", "year", "rows_checked", "rows_failed"])
    failures = (
        pd.concat(fails, ignore_index=True)
        if fails
        else pd.DataFrame(columns=["rule_id", "table", "row_num"])
    )
    return results, timeline, failures


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
