"""Nightly audit metrics (Phase 5, task 5.1): one tidy row per metric per run, appended so Power BI can chart the trend."""

from __future__ import annotations

import json

import pandas as pd

from hcls import config
from hcls.recon import claims

COLUMNS = ["run_ts", "git_sha", "metric", "value", "unit", "area"]


def _scalar(df: pd.DataFrame, rule: str, col: str = "rows_failed") -> float:
    s = df.loc[df["rule_id"] == rule, col]
    return float(s.iloc[0]) if len(s) else 0.0


def compute(gold, alerts: dict | None = None) -> pd.DataFrame:
    """Headline metrics from the gold files. Every number is read from a file, never typed in."""
    sc = pd.read_csv(gold / "dq_scorecard.csv")
    live = sc[sc["severity"] != "Info"]
    detail = pd.read_csv(gold / "recon_claims.csv")
    buckets = pd.read_csv(gold / "recon_buckets.csv").set_index("bucket")
    ev = claims.expected_value(detail)
    run_ts, sha = sc["run_ts"].iloc[0], sc["git_sha"].iloc[0]
    rows: list[tuple[str, float, str, str]] = [
        ("rules_in_scope", len(live), "rules", "Data quality"),
        ("rules_failing", int((live["rows_failed"] > 0).sum()), "rules", "Data quality"),
        ("rule_pass_rate", round(100 * (live["rows_failed"] == 0).mean(), 1), "%", "Data quality"),
        (
            "critical_rules_failing",
            int(((live["severity"] == "Critical") & (live["rows_failed"] > 0)).sum()),
            "rules",
            "Data quality",
        ),
        (
            "high_rules_failing",
            int(((live["severity"] == "High") & (live["rows_failed"] > 0)).sum()),
            "rules",
            "Data quality",
        ),
        ("c01_claims_without_approved_amount", _scalar(sc, "C01"), "rows", "Confirmed issues"),
        ("c02_visits_without_appointment", _scalar(sc, "C02"), "rows", "Confirmed issues"),
        ("c03_records_without_medication", _scalar(sc, "C03"), "rows", "Confirmed issues"),
        ("claims_submitted_total", round(float(detail["submitted_amount"].sum()), 2), "USD", "Finance"),
        ("paid_certain", float(buckets.loc["Paid", "amount"]), "USD", "Finance"),
        ("pipeline_estimated", float(buckets.loc["Pipeline", "amount"]), "USD", "Finance"),
        ("pipeline_expected", float(ev["expected"]), "USD", "Finance"),
        ("pipeline_ceiling", float(ev["ceiling_no_denials"]), "USD", "Finance"),
        ("claims_on_dq_hold", int(buckets.loc["DQ Hold", "claims"]), "claims", "Finance"),
    ]
    for name, f, col in (
        ("backfill_c03_applied", "backfill_summary.csv", "applied_to_copy"),
        ("backfill_c02_applied", "backfill_summary.csv", "applied_to_copy"),
    ):
        p = gold / f
        if p.exists():
            s = pd.read_csv(p).set_index("rule_id")
            rows.append((name, float(s.loc[name.split("_")[1].upper(), col]), "rows", "Remediation"))
    p = gold / "validator_catch.csv"
    if p.exists():
        rows.append(
            (
                "validators_firing",
                int((pd.read_csv(p)["rows_it_would_reject"] > 0).sum()),
                "checks",
                "Prevention",
            )
        )
    p = gold / "validator_violations.csv"
    if p.exists():
        v = pd.read_csv(p)
        rows.append(
            (
                "rows_validators_would_reject",
                int(v.groupby(["table", "row_num"]).ngroups),
                "rows",
                "Prevention",
            )
        )
    p = gold / "recon_timing.csv"
    if p.exists():
        rows.append(("recon_seconds", float(pd.read_csv(p)["seconds"].iloc[0]), "seconds", "Operations"))
    if alerts is None:
        ap = config.path("outputs") / "alerts.json"
        alerts = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else {}
    if alerts:
        rows.append(("alerts_open", len(alerts.get("alerts", [])), "alerts", "Operations"))
    out = pd.DataFrame(rows, columns=["metric", "value", "unit", "area"])
    out.insert(0, "git_sha", sha)
    out.insert(0, "run_ts", run_ts)
    return out[COLUMNS]


def append(metrics: pd.DataFrame, gold) -> pd.DataFrame:
    """Append this run to audit_metrics.csv. Re-running the same run_ts replaces it instead of duplicating."""
    path = gold / "audit_metrics.csv"
    if path.exists():
        old = pd.read_csv(path)
        old = old[old["run_ts"] != metrics["run_ts"].iloc[0]]
        metrics = pd.concat([old, metrics], ignore_index=True)
    metrics.to_csv(path, index=False)
    return metrics
