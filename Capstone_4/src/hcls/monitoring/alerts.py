"""Monitoring alerts (Phase 4, task 4.5; SPEC section 11). Writes outputs/alerts.json.

threshold : a Critical rule fails on more than `critical_threshold_pct` of its records
drift     : a rule's failure count changes by more than `drift_pct` against the previous run
sla       : reconciliation took longer than `recon_sla_seconds`
Job failure alerts come from the Databricks job definitions (email_notifications), not from this module.
"""

from __future__ import annotations

import json

import pandas as pd

from hcls import config


def thresholds() -> dict:
    cfg = config.load_config()["alerts"]
    return {
        "critical_threshold_pct": float(cfg["critical_threshold_pct"]),
        "drift_pct": float(cfg["drift_pct"]),
        "recon_sla_seconds": float(cfg["recon_sla_seconds"]),
    }


def threshold_alerts(sc: pd.DataFrame, limit: float) -> list[dict]:
    crit = sc[(sc["severity"] == "Critical") & (sc["pct_failed"] > limit)]
    return [
        {
            "type": "threshold",
            "rule_id": r.rule_id,
            "notify": r.stakeholder,
            "value": float(r.pct_failed),
            "limit": limit,
            "message": f"Critical rule {r.rule_id} fails on {r.pct_failed:.1f}% of {r.table} ({r.rows_failed} of {r.rows_checked}), above {limit:g}%",
        }
        for r in crit.itertuples()
    ]


def drift_alerts(sc: pd.DataFrame, prev: pd.DataFrame | None, limit: float) -> list[dict]:
    if prev is None or prev.empty:
        return []
    cur = sc.set_index("rule_id")["rows_failed"]
    old = prev.set_index("rule_id")["rows_failed"]
    out = []
    for rule in cur.index.intersection(old.index):
        n, o = int(cur[rule]), int(old[rule])
        if n == o:
            continue
        pct = 100.0 if o == 0 else 100.0 * abs(n - o) / o
        if pct > limit:
            row = sc.set_index("rule_id").loc[rule]
            out.append(
                {
                    "type": "drift",
                    "rule_id": rule,
                    "notify": row["stakeholder"],
                    "value": round(pct, 1),
                    "limit": limit,
                    "message": f"{rule} failures moved from {o} to {n} ({pct:.1f}% change, limit {limit:g}%)",
                }
            )
    return out


def sla_alerts(timing: pd.DataFrame | None, sla: float) -> list[dict]:
    if timing is None or timing.empty:
        return []
    row = timing.iloc[0]
    if float(row["seconds"]) <= sla:
        return []
    return [
        {
            "type": "sla",
            "rule_id": "recon",
            "notify": "Finance",
            "value": float(row["seconds"]),
            "limit": sla,
            "message": f"Reconciliation took {float(row['seconds']):.0f}s, above the {sla:g}s limit",
        }
    ]


def evaluate(
    sc: pd.DataFrame,
    prev: pd.DataFrame | None = None,
    timing: pd.DataFrame | None = None,
    limits: dict | None = None,
) -> dict:
    from hcls.dq.scorecard import git_sha

    t = limits or thresholds()
    alerts = (
        threshold_alerts(sc, t["critical_threshold_pct"])
        + drift_alerts(sc, prev, t["drift_pct"])
        + sla_alerts(timing, t["recon_sla_seconds"])
    )
    by_type = pd.Series([a["type"] for a in alerts], dtype=str).value_counts().to_dict()
    return {
        "as_of_date": config.as_of_date().isoformat(),
        "run_ts": str(sc["run_ts"].iloc[0]) if len(sc) and "run_ts" in sc else None,
        "git_sha": git_sha(),
        "thresholds": t,
        "previous_run_available": prev is not None and not prev.empty,
        "status": "ALERT" if alerts else "OK",
        "counts": by_type,
        "alerts": alerts,
    }


def write_alerts(result: dict, path=None):
    path = path or config.outputs_dir() / "alerts.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return path
