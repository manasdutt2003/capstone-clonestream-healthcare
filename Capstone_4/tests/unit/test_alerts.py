"""Alert rules: Critical threshold, drift against the previous run, reconciliation SLA."""

import json

import pandas as pd

from hcls.monitoring import alerts

LIMITS = {"critical_threshold_pct": 5.0, "drift_pct": 10.0, "recon_sla_seconds": 300.0}


def sc(rows):
    df = pd.DataFrame(
        rows, columns=["rule_id", "table", "severity", "stakeholder", "rows_failed", "rows_checked"]
    )
    df["pct_failed"] = 100 * df["rows_failed"] / df["rows_checked"]
    df["run_ts"] = "2026-10-21T00:00:00Z"
    return df


NOW = sc(
    [
        ("C01", "Insurance_Claims", "Critical", "Finance", 90, 250),
        ("C09", "Patients", "Critical", "PatientCare", 4, 100),  # 4%: under the limit
        ("A99", "Billing", "High", "Finance", 200, 250),  # not Critical: no threshold alert
        ("X1", "Visits", "Low", "Ops", 10, 100),
    ]
)


def test_only_critical_rules_over_the_limit_alert():
    out = alerts.threshold_alerts(NOW, 5.0)
    assert (
        [a["rule_id"] for a in out] == ["C01"] and out[0]["notify"] == "Finance" and out[0]["value"] == 36.0
    )


def test_limit_is_strict():
    exactly = sc([("C01", "Insurance_Claims", "Critical", "Finance", 5, 100)])
    assert alerts.threshold_alerts(exactly, 5.0) == []


def test_drift_needs_a_previous_run_and_a_change_over_the_limit():
    assert alerts.drift_alerts(NOW, None, 10.0) == []
    prev = sc(
        [
            ("C01", "Insurance_Claims", "Critical", "Finance", 90, 250),  # unchanged
            ("C09", "Patients", "Critical", "PatientCare", 3, 100),  # 3 -> 4 = +33%
            ("A99", "Billing", "High", "Finance", 195, 250),  # 195 -> 200 = +2.6%: under the limit
            ("X1", "Visits", "Low", "Ops", 0, 100),  # 0 -> 10: new failures
        ]
    )
    got = {a["rule_id"]: a for a in alerts.drift_alerts(NOW, prev, 10.0)}
    assert set(got) == {"C09", "X1"} and got["X1"]["value"] == 100.0 and got["C09"]["value"] == 33.3


def test_sla_alert_only_when_over():
    assert alerts.sla_alerts(pd.DataFrame([{"seconds": 120.0}]), 300) == []
    assert alerts.sla_alerts(pd.DataFrame([{"seconds": 301.0}]), 300)[0]["type"] == "sla"
    assert alerts.sla_alerts(None, 300) == []


def test_evaluate_status_counts_and_file(tmp_path):
    ok = alerts.evaluate(sc([("C01", "Insurance_Claims", "Critical", "Finance", 1, 250)]), None, None, LIMITS)
    assert ok["status"] == "OK" and ok["alerts"] == [] and not ok["previous_run_available"]
    bad = alerts.evaluate(NOW, NOW, pd.DataFrame([{"seconds": 400.0}]), LIMITS)
    assert (
        bad["status"] == "ALERT"
        and bad["counts"] == {"threshold": 1, "sla": 1}
        and bad["previous_run_available"]
    )
    path = alerts.write_alerts(bad, tmp_path / "alerts.json")
    loaded = json.loads(path.read_text())
    assert (
        loaded["thresholds"] == LIMITS and len(loaded["alerts"]) == 2 and loaded["as_of_date"] == "2026-10-21"
    )


def test_limits_come_from_config():
    t = alerts.thresholds()
    assert t == {"critical_threshold_pct": 5.0, "drift_pct": 10.0, "recon_sla_seconds": 300.0}
