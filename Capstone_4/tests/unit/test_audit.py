"""Audit trail, Power BI export, memos and audit pack."""

import datetime as dt
import re

import pandas as pd
import pytest

from hcls import cli, config
from hcls.audit import audit_log, facts, memos, pack, powerbi


def test_manifest_hashes_every_file_and_verify_spots_an_edit(tmp_path):
    (tmp_path / "a.csv").write_text("x\n1\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.csv").write_text("y\n2\n")
    (tmp_path / "audit_log.csv").write_text("ignored")  # the log cannot fingerprint itself
    man = audit_log.manifest(tmp_path)
    assert list(man["file"]) == ["a.csv", "sub/b.csv"]
    assert man["sha256"].str.len().eq(64).all()
    man.to_csv(tmp_path / "audit_outputs.csv", index=False)
    assert audit_log.verify(tmp_path) == []
    (tmp_path / "a.csv").write_text("x\n999\n")
    (tmp_path / "c.csv").write_text("new\n")
    (tmp_path / "sub" / "b.csv").unlink()
    assert audit_log.verify(tmp_path) == ["a.csv", "c.csv", "sub/b.csv"]


def test_digest_changes_when_any_file_changes(tmp_path):
    (tmp_path / "a.csv").write_text("1")
    d1 = audit_log.digest(audit_log.manifest(tmp_path))
    assert d1 == audit_log.digest(audit_log.manifest(tmp_path))  # stable
    (tmp_path / "a.csv").write_text("2")
    assert audit_log.digest(audit_log.manifest(tmp_path)) != d1


def test_log_row_is_appended_not_rewritten(tmp_outputs):
    t0 = dt.datetime(2026, 10, 21, 2, 0, tzinfo=dt.timezone.utc)
    for job in ("dq", "alerts"):
        audit_log.append_entry(audit_log.build_entry(job, t0, t0 + dt.timedelta(seconds=5), "ok"))
    log = pd.read_csv(config.outputs_dir("gold") / "audit_log.csv")
    assert list(log["job"]) == ["dq", "alerts"]
    assert list(log.columns) == audit_log.LOG_COLUMNS
    assert (log["seconds"] == 5).all() and log["run_id"].is_unique


def test_a_failing_command_is_logged_as_failed(tmp_outputs, monkeypatch):
    def boom():
        raise RuntimeError("nope")

    monkeypatch.setitem(cli.COMMANDS, "flash", boom)
    with pytest.raises(RuntimeError):
        cli._run("flash")
    log = pd.read_csv(config.outputs_dir("gold") / "audit_log.csv")
    assert list(log["status"]) == ["failed"] and list(log["job"]) == ["flash"]


@pytest.mark.parametrize(
    "df",
    [
        pd.DataFrame({"email": ["a@b.com"]}),
        pd.DataFrame({"patient_phone": ["x"]}),
        pd.DataFrame({"date_of_birth": ["1990-01-01"]}),
        pd.DataFrame({"note": ["write to jo@example.com"]}),
        pd.DataFrame({"note": ["call (555) 123-4567"]}),
        pd.DataFrame({"first_name": ["x"]}),
    ],
)
def test_pii_check_refuses_personal_data(df):
    with pytest.raises(powerbi.PiiError):
        powerbi.check_no_pii("t", df)


def test_pii_check_allows_ids_and_rule_names():
    powerbi.check_no_pii(
        "t", pd.DataFrame({"patient_id": ["1"], "name": ["claim patient differs"], "amount": [1.0]})
    )


def test_waterfall_walks_from_submitted_down_to_paid():
    d = pd.DataFrame(
        {
            "bucket": ["Paid", "Paid", "Denied", "Pipeline", "Under appeal", "DQ Hold"],
            "submitted_amount": [100.0, 50.0, 30.0, 40.0, 10.0, -5.0],
            "adjustment_amount": [20.0, 10.0, 0, 0, 0, 0],
        }
    )
    w = powerbi.waterfall(d)
    assert w.iloc[0]["amount"] == 225.0 and w.iloc[0]["kind"] == "total"
    assert (
        w.iloc[-1]["step"].startswith("Paid") and w.iloc[-1]["amount"] == 120.0
    )  # 150 submitted on paid claims less 30 reductions
    assert w["amount"].iloc[:-1].sum() == w.iloc[-1]["amount"]  # the steps land exactly on the result
    assert list(w["sort"]) == list(range(1, len(w) + 1))


def test_dimensions_cover_every_severity_and_bucket():
    assert set(powerbi.dim_severity()["severity"]) == {"Critical", "High", "Medium", "Low", "Info"}
    assert set(powerbi.dim_bucket()["confidence_group"]) == {"Certain", "Estimated", "Excluded"}
    assert len(powerbi.remediation_tracker()) == 9 and set(powerbi.remediation_tracker()["status"]) == {
        "Open"
    }


def _facts():
    return {
        "as_of": "2026-10-21",
        "rule": {
            k: {"rows": 5, "of": 10, "pct": 50.0, "name": "n", "table": "t"}
            for k in ("C01", "C02", "C03", "A12", "A16", "A24", "A28", "A30", "A31", "A02")
        },
        "bucket": {
            k: {"claims": 1, "amount": 1000.0}
            for k in ("Paid", "Adjustment", "Denied", "Pipeline", "Under appeal", "DQ Hold")
        },
        "expected": {
            "expected": 1_170_000.0,
            "low": 1_040_000.0,
            "high": 1_300_000.0,
            "ceiling_no_denials": 1_680_000.0,
        },
        "link_health": pd.DataFrame(
            {"linked_rows": [250], "same_patient": [0]}, index=["Insurance_Claims -> Billing"]
        ),
        "backfill": pd.DataFrame(
            {"applied_to_copy": [0, 0], "records_failing_before": [40, 123], "conflicts_with_plan": [2, 0]},
            index=["C03", "C02"],
        ),
        "alerts": {"alerts": [1, 2], "status": "ALERT", "counts": {"threshold": 2}},
        "submitted_total": 6000.0,
        "claims_total": 6,
        "pipeline_old": 1,
        "pipeline_claims": 2,
        "paid_date_flagged": 3,
        "paid_claims": 4,
        "rules_run": 441,
        "tables_total": 19,
        "findings": 164,
        "critical_high": 28,
        "severity": {"Critical": 5, "High": 23},
        "tables_with_critical_high": 11,
        "sentinel_rows": 116,
        "sentinel_tables": 8,
        "validators": 49,
        "validator_rows": 1903,
    }


@pytest.mark.parametrize("name", list(memos.MEMOS))
def test_memos_are_one_page_and_free_of_unfilled_placeholders(name):
    text = memos.MEMOS[name](_facts())
    assert 15 <= len(text.splitlines()) <= 45  # about one page
    assert not re.search(r"\{[a-z_\[\]\"' ]+\}|\bnan\b|\bNone\b", text.replace('"None"', ""))
    assert text.startswith("# Memo for")


def test_finance_memo_never_presents_the_ceiling_as_the_expectation():
    text = memos.finance(_facts())
    expected_line = next(line for line in text.splitlines() if "We expect about" in line)
    assert (
        "$1.17M" in expected_line.split("The earlier")[0]
        and "$1.68M" not in expected_line.split("The earlier")[0]
    )
    assert "most it could be" in expected_line and "Do not refund yet" in text


@pytest.mark.realdata
def test_pack_and_memos_from_real_gold(tmp_outputs):
    assert cli.main(["all"]) == 0
    gold = config.outputs_dir("gold")
    f = facts.collect(gold)
    text = pack.render(f, pd.read_csv(gold / "audit_log.csv"), pd.read_csv(gold / "audit_metrics.csv"))
    for i in range(1, 9):
        assert f"| {i} |" in text
    for n in ("## 1.", "## 3.", "## 5.", "## 8.", "## 10."):
        assert n in text
    assert "$1,945,489" in text and "0 of 40" in text and "0 of 123" in text and "Not determinable" in text
    assert audit_log.verify(gold) == []  # nothing changed since the audit step
    # every table[column] named in the DAX file exists in the exported tables
    tables = powerbi.build(gold)
    dax = (config.project_root() / "powerbi" / "measures.dax.md").read_text()
    refs = set(re.findall(r"\b((?:fact|dim)_\w+)\[(\w+)\]", dax))
    assert len(refs) > 20
    missing = [(t, c) for t, c in refs if t not in tables or c not in tables[t].columns]
    assert not missing, missing
    # tampering with an output is detected, and the verify command exits non-zero
    from hcls.audit import verify

    assert verify.main() == 0
    (gold / "dq_timeline.csv").write_text("tampered\n")
    assert audit_log.verify(gold) == ["dq_timeline.csv"]
    assert verify.main() == 1
