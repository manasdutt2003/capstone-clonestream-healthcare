"""Scorecard, timeline, history and cross-checks (Phase 1, task 1.5 / 1.6)."""

from __future__ import annotations

import subprocess

import pandas as pd

from hcls import config
from hcls.dq.runner import now_utc
from hcls.ingest import data_columns

# Rule families whose failing rows are worth flagging on each silver record.
FLAGGED_PREFIXES = ("R-", "F-", "S-", "V-", "B-", "X-", "J-")


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=config.project_root(),
            timeout=5,
        )
        return out.stdout.strip() or "nogit"
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def build_scorecard(results: pd.DataFrame, timeline: pd.DataFrame, run_ts: str | None = None) -> pd.DataFrame:
    cfg = config.load_config()["scoring"]
    sc = results.copy()
    sc["pct_failed"] = (
        (sc["rows_failed"] / sc["rows_checked"].where(sc["rows_checked"] > 0) * 100).fillna(0).round(2)
    )
    sc["impact_score"] = (
        sc["severity"].map(cfg["severity_weight"])
        * sc["pct_failed"]
        * sc["stakeholder"].map(cfg["stakeholder_weight"])
    ).round(2)
    seen = (
        timeline[timeline["rows_failed"] > 0]
        .groupby("rule_id")["year"]
        .agg(first_seen="min", last_seen="max")
    )
    sc = sc.merge(seen, on="rule_id", how="left")
    sc["run_ts"] = run_ts or now_utc()
    sc["git_sha"] = git_sha()
    order = ["Critical", "High", "Medium", "Low", "Info"]
    sc["_sev"] = sc["severity"].map({s: i for i, s in enumerate(order)})
    sc = sc.sort_values(["impact_score", "_sev", "rule_id"], ascending=[False, True, True]).drop(
        columns="_sev"
    )
    sc["rank"] = range(1, len(sc) + 1)
    return sc[
        [
            "rank",
            "rule_id",
            "table",
            "column",
            "check_type",
            "severity",
            "stakeholder",
            "name",
            "rows_checked",
            "rows_failed",
            "pct_failed",
            "impact_score",
            "impact_statement",
            "first_seen",
            "last_seen",
            "source",
            "run_ts",
            "git_sha",
        ]
    ].reset_index(drop=True)


def timeline_table(timeline: pd.DataFrame) -> pd.DataFrame:
    t = timeline.copy()
    t["pct_failed"] = (
        (t["rows_failed"] / t["rows_checked"].where(t["rows_checked"] > 0) * 100).fillna(0).round(2)
    )
    return t


def history_row(scorecard: pd.DataFrame) -> pd.DataFrame:
    h = scorecard[["rule_id", "rows_checked", "rows_failed", "run_ts", "git_sha"]].copy()
    return h


def append_history(scorecard: pd.DataFrame) -> pd.DataFrame:
    path = config.outputs_dir("gold") / "dq_history.csv"
    new = history_row(scorecard)
    if path.exists():
        old = pd.read_csv(path)
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(path, index=False)
    return new


# ----------------------------------------------------------------------------- cross-checks


def ri_crosscheck(bronze: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compare the workbook's own Referential_Integrity sheet with what we compute from the data."""
    from hcls.dq.rules import FOREIGN_KEYS

    ri = bronze["Referential_Integrity"]
    fk_by_key = {(c, col): (p, pc) for c, col, p, pc in FOREIGN_KEYS}
    rows = []
    for _, r in ri.iterrows():
        key = (r["table_name"], r["fk_column"])
        parent, pcol = fk_by_key.get(key, (r["referenced_table"], None))
        child_vals = bronze[r["table_name"]][r["fk_column"]]
        parent_ids = (
            set(pd.to_numeric(bronze[parent][pcol], errors="coerce").dropna().astype("int64"))
            if pcol
            else set()
        )
        bad_vals = set()
        bad_rows = 0
        for v in child_vals:
            if v is None:
                continue
            try:
                ok = int(float(v)) in parent_ids
            except ValueError:
                ok = False
            if not ok:
                bad_rows += 1
                bad_vals.add(v)
        sheet_types = int(r["violation_count_types"])
        rows.append(
            {
                "table": r["table_name"],
                "fk_column": r["fk_column"],
                "references": r["referenced_table"],
                "sheet_violation_types": sheet_types,
                "engine_violation_types": len(bad_vals),
                "engine_violating_rows": bad_rows,
                "verdict": "matches"
                if sheet_types == len(bad_vals)
                else ("sheet over-reports" if sheet_types > len(bad_vals) else "sheet under-reports"),
            }
        )
    return pd.DataFrame(rows)


def cleaning_effect(raw_results: pd.DataFrame, clean_results: pd.DataFrame) -> pd.DataFrame:
    m = raw_results[["rule_id", "table", "column", "check_type", "severity", "rows_failed"]].merge(
        clean_results[["rule_id", "rows_failed"]], on="rule_id", suffixes=("_raw", "_clean"), how="left"
    )
    m["fixed"] = m["rows_failed_raw"] - m["rows_failed_clean"]
    return m


def add_flags(
    silver: dict[str, pd.DataFrame], failures: pd.DataFrame, changes: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Attach `_dq_flags` (residual failing rule ids) and `_cleaned_cols` to every silver row."""
    out = {}
    flagged = failures[
        failures["rule_id"].str.startswith(FLAGGED_PREFIXES) | ~failures["rule_id"].str.contains("-")
    ]
    by_row = flagged.groupby(["table", "row_num"])["rule_id"].agg(lambda s: "|".join(sorted(s)))
    ch = (
        changes.groupby(["table", "row_num"])["column"].agg(lambda s: ",".join(sorted(set(s))))
        if len(changes)
        else pd.Series(dtype=object)
    )
    for name, df in silver.items():
        df = df.copy()
        keys = list(zip([name] * len(df), df["_row_num"], strict=True))
        df["_dq_flags"] = [by_row.get(k) for k in keys]
        df["_cleaned_cols"] = [ch.get(k) for k in keys] if len(ch) else None
        out[name] = df
    return out


def table_summary(scorecard: pd.DataFrame) -> pd.DataFrame:
    s = scorecard[(scorecard["rows_failed"] > 0) & scorecard["severity"].isin(["Critical", "High", "Medium"])]
    g = s.groupby("table").agg(
        rules_failing=("rule_id", "count"),
        critical=("severity", lambda x: (x == "Critical").sum()),
        high=("severity", lambda x: (x == "High").sum()),
        total_failed_cells=("rows_failed", "sum"),
    )
    return g.sort_values(["critical", "high", "total_failed_cells"], ascending=False).reset_index()


__all__ = [
    "build_scorecard",
    "timeline_table",
    "append_history",
    "ri_crosscheck",
    "cleaning_effect",
    "add_flags",
    "table_summary",
    "data_columns",
]
