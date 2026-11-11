"""Every number the memos and the audit pack quote, read from the gold files in one place (never typed by hand)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hcls import config
from hcls.recon import claims


def usd(x: float, short: bool = False) -> str:
    if short:
        return f"${x / 1e6:,.2f}M"
    return f"${x:,.0f}"


def collect(gold: Path | None = None) -> dict:
    gold = gold or config.outputs_dir("gold")
    sc = pd.read_csv(gold / "dq_scorecard.csv")
    live = sc[sc["severity"] != "Info"]
    found = live[live["rows_failed"] > 0]
    detail = pd.read_csv(gold / "recon_claims.csv")
    bk = pd.read_csv(gold / "recon_buckets.csv").set_index("bucket")
    ev = claims.expected_value(detail)
    rc = gold / "rootcause"
    tl = pd.read_csv(rc / "timeline_summary.csv").set_index("rule_id")
    hyp = pd.read_csv(rc / "hypotheses.csv")
    lin = pd.read_csv(rc / "lineage.csv")
    lh = pd.read_csv(rc / "link_health.csv").set_index("link")
    sent = pd.read_csv(rc / "sentinel_ids.csv")
    bf = pd.read_csv(gold / "backfill_summary.csv").set_index("rule_id")
    vc = pd.read_csv(gold / "validator_catch.csv")
    vv = pd.read_csv(gold / "validator_violations.csv")
    ap = config.path("outputs") / "alerts.json"
    alerts = (
        json.loads(ap.read_text(encoding="utf-8"))
        if ap.exists()
        else {"status": "n/a", "alerts": [], "counts": {}}
    )
    paid = detail[detail["bucket"] == "Paid"]
    pipe = detail[detail["bucket"] == "Pipeline"]

    def rule(r: str) -> dict:
        row = sc[sc["rule_id"] == r].iloc[0]
        return {
            "rows": int(row["rows_failed"]),
            "of": int(row["rows_checked"]),
            "pct": float(row["pct_failed"]),
            "name": row["name"],
            "table": row["table"],
        }

    hi = found[found["severity"].isin(["Critical", "High"])]
    return {
        "as_of": config.as_of_date().isoformat(),
        "run_ts": sc["run_ts"].iloc[0],
        "git_sha": sc["git_sha"].iloc[0],
        "rules_run": len(sc),
        "findings": len(found),
        "severity": found["severity"].value_counts().to_dict(),
        "critical_high": len(hi),
        "tables_with_critical_high": int(hi["table"].nunique()),
        "tables_total": int(sc["table"].nunique()),
        "rule": {
            r: rule(r)
            for r in ("C01", "C02", "C03", "A02", "A30", "A38", "A03", "A31", "A12", "A16", "A24", "A28")
        },
        "top": found.sort_values("impact_score", ascending=False).head(10),
        "found": found,
        "bucket": {b: {"claims": int(r["claims"]), "amount": float(r["amount"])} for b, r in bk.iterrows()},
        "submitted_total": float(detail["submitted_amount"].sum()),
        "claims_total": len(detail),
        "expected": ev,
        "paid_claims": len(paid),
        "paid_date_flagged": int(paid["date_flags"].notna().sum()),
        "pipeline_claims": len(pipe),
        "pipeline_old": int((pipe["age_days"] > 365).sum()),
        "timeline": tl,
        "hypotheses": hyp,
        "verdicts": hyp["verdict"].value_counts().to_dict(),
        "links": lin["status"].value_counts().to_dict(),
        "links_total": len(lin),
        "link_health": lh,
        "sentinel_rows": int(sent["rows_affected"].sum()),
        "sentinel_tables": int(sent["table_name"].nunique()),
        "backfill": bf,
        "validators": len(vc),
        "validators_firing": int((vc["rows_it_would_reject"] > 0).sum()),
        "validator_rows": int(vv.groupby(["table", "row_num"]).ngroups),
        "alerts": alerts,
    }
