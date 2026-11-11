"""Power BI-ready tables (Phase 5, task 5.2): a curated, PII-free copy of the gold data with stable names.

Power BI reads `outputs/powerbi/*.csv`. Names, e-mails, phones, addresses and dates of birth never reach this folder; a
check refuses to write a table that has such a column or value. Patient identifiers are kept (ids only, NFR6).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from hcls import config
from hcls.recon import claims
from hcls.remediation import plan

FORBIDDEN_TOKENS = {
    "email",
    "phone",
    "address",
    "dob",
    "birth",
    "ssn",
    "zip",
    "street",
    "firstname",
    "lastname",
    "fullname",
}
FORBIDDEN_COLUMNS = {"first_name", "last_name", "full_name", "emergency_contact_name", "contact_name", "user"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\(\d{3}\) \d{3}-\d{4}")


class PiiError(ValueError):
    pass


def check_no_pii(name: str, df: pd.DataFrame) -> None:
    for c in df.columns:
        low = c.lower()
        if low in FORBIDDEN_COLUMNS or FORBIDDEN_TOKENS & set(low.split("_")):
            raise PiiError(f"{name}: column '{c}' looks like personal data")
    for c in df.select_dtypes(include=["object", "string"]).columns:
        s = df[c].dropna().astype(str)
        if s.str.contains(EMAIL).any() or s.str.contains(PHONE).any():
            raise PiiError(f"{name}: column '{c}' holds an e-mail address or phone number")


def _read(gold: Path, f: str) -> pd.DataFrame:
    return pd.read_csv(gold / f)


def remediation_tracker() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "group": g["id"],
                "title": g["title"],
                "rules": ", ".join(g["rules"]),
                "action": g["action"],
                "owner": g["owner"],
                "effort": g["effort"],
                "risk": g["risk"],
                "status": "Open",
            }
            for g in plan.MATRIX
        ]
    )


def dim_severity() -> pd.DataFrame:
    w = config.load_config()["scoring"]["severity_weight"]
    order = ["Critical", "High", "Medium", "Low", "Info"]
    return pd.DataFrame({"severity": order, "sort": range(1, 6), "weight": [w[s] for s in order]})


def dim_bucket() -> pd.DataFrame:
    rows = [
        ("Paid", 1, "Certain"),
        ("Adjustment", 2, "Certain"),
        ("Denied", 3, "Certain"),
        ("Under appeal", 4, "Estimated"),
        ("Pipeline", 5, "Estimated"),
        ("Approved, not yet paid", 6, "Estimated"),
        ("DQ Hold", 7, "Excluded"),
    ]
    return pd.DataFrame(rows, columns=["bucket", "sort", "confidence_group"])


def waterfall(detail: pd.DataFrame) -> pd.DataFrame:
    """From everything submitted down to what is certain: each step is the dollars taken out."""
    amt = detail.groupby("bucket")["submitted_amount"].sum()
    total = float(detail["submitted_amount"].sum())
    adj = float(detail["adjustment_amount"].sum())
    steps = [
        ("Total submitted", total, "total"),
        ("Insurer reductions (adjustment)", -adj, "step"),
        ("Denied", -float(amt.get("Denied", 0)), "step"),
        ("Under appeal", -float(amt.get("Under appeal", 0)), "step"),
        ("Open claims (pipeline)", -float(amt.get("Pipeline", 0)), "step"),
        ("Approved, not yet paid", -float(amt.get("Approved, not yet paid", 0)), "step"),
        ("Held for data review", -float(amt.get("DQ Hold", 0)), "step"),
    ]
    paid = total + sum(a for _, a, k in steps if k == "step")
    steps.append(("Paid (certain)", paid, "result"))
    out = pd.DataFrame(steps, columns=["step", "amount", "kind"])
    out.insert(1, "sort", range(1, len(out) + 1))
    return out


def build(gold: Path | None = None) -> dict[str, pd.DataFrame]:
    gold = gold or config.outputs_dir("gold")
    detail = _read(gold, "recon_claims.csv")
    keep = [
        "claim_id",
        "patient_id",
        "claim_status",
        "submitted_amount",
        "approved_amount",
        "submitted_date",
        "approved_date",
        "paid_date",
        "bucket",
        "confidence",
        "age_days",
        "date_flags",
        "hold_reason",
    ]
    tables = {
        "fact_scorecard": _read(gold, "dq_scorecard.csv"),
        "fact_timeline": _read(gold, "dq_timeline.csv"),
        "fact_history": _read(gold, "dq_history.csv"),
        "fact_claims": detail[keep],
        "fact_recon_buckets": _read(gold, "recon_buckets.csv"),
        "fact_waterfall": waterfall(detail),
        "fact_pipeline_aging": claims.pipeline_aging(detail),
        "fact_link_health": _read(gold, "rootcause/lineage.csv"),
        "fact_payment_links": _read(gold, "rootcause/link_health.csv"),
        "fact_hypotheses": _read(gold, "rootcause/hypotheses.csv"),
        "fact_timeline_tests": _read(gold, "rootcause/timeline_summary.csv"),
        "fact_remediation": remediation_tracker(),
        "fact_backfill": _read(gold, "backfill_summary.csv"),
        "fact_validators": _read(gold, "validator_catch.csv"),
        "fact_metrics": _read(gold, "audit_metrics.csv"),
        "dim_severity": dim_severity(),
        "dim_bucket": dim_bucket(),
    }
    if (gold / "audit_log.csv").exists():
        tables["fact_audit_log"] = _read(gold, "audit_log.csv").drop(columns=["user"], errors="ignore")
    return tables


def write(gold: Path | None = None) -> pd.DataFrame:
    tables = build(gold)
    out = config.outputs_dir("powerbi")
    rows = []
    for name, df in tables.items():
        check_no_pii(name, df)
        df.to_csv(out / f"{name}.csv", index=False)
        rows.append({"table": name, "rows": len(df), "columns": len(df.columns)})
    man = pd.DataFrame(rows)
    man.to_csv(out / "manifest.csv", index=False)
    return man
