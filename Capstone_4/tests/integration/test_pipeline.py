"""Integration tests: ingest -> clean -> DQ -> flash -> workbook end to end, writing only to a temp folder."""

import json

import openpyxl
import pandas as pd
import pytest

from hcls import cli, config, ingest, standardise
from hcls.export_clean import write_clean_workbook

pytestmark = pytest.mark.realdata


def test_clean_workbook_keeps_every_row_and_has_real_types(bronze, cleaned, tmp_path):
    silver, changes = cleaned
    path = write_clean_workbook(silver, changes, tmp_path / "clean.xlsx")
    wb = openpyxl.load_workbook(path, read_only=True)
    assert len(wb.sheetnames) == 21 and wb.sheetnames[-1] == "Cleaning_Summary"
    sheets = pd.read_excel(path, sheet_name=None)
    for name, df in bronze.items():
        assert len(sheets[name]) == len(df), f"{name} lost or gained rows"
        assert list(sheets[name].columns) == ingest.data_columns(df)
    patients = sheets["Patients"]
    assert str(patients["date_of_birth"].dtype).startswith("datetime64")
    assert set(patients["gender"].dropna()) <= {"Male", "Female", "Non-Binary"}
    assert patients["height_cm"].dropna().between(50, 250).all()
    hospitals = pd.read_excel(path, sheet_name="Hospitals", dtype={"zip_code": str})
    assert "02101" in set(hospitals["zip_code"])  # leading zero survives


def test_full_cli_run_builds_every_layer_and_doc(tmp_outputs):
    assert cli.main(["all"]) == 0
    out = tmp_outputs / "outputs"
    for layer in ("bronze", "silver"):
        assert len(list((out / layer).glob("*.parquet"))) == 20
    gold = out / "gold"
    for f in (
        "dq_scorecard.csv",
        "dq_timeline.csv",
        "dq_history.csv",
        "ri_crosscheck.csv",
        "change_log.csv",
        "cleaning_summary.csv",
        "cleaning_effect.csv",
        "finance_flash_by_status.csv",
    ):
        assert (gold / f).exists(), f
    assert (tmp_outputs / "clean" / "HCLS_cleaned.xlsx").exists()
    docs = tmp_outputs / "docs"
    for f in (
        "backfill_summary.csv",
        "backfill_c03.csv",
        "backfill_c02.csv",
        "validator_catch.csv",
        "validator_violations.csv",
    ):
        assert (gold / f).exists(), f
    assert (docs / "04_remediation_plan.md").exists()
    alerts = json.loads((out / "alerts.json").read_text())
    assert alerts["status"] == "ALERT" and alerts["counts"] == {"threshold": 5}  # the five Critical rules
    for f in ("hypotheses.csv", "timeline_summary.csv", "link_health.csv", "lineage.csv"):
        assert (gold / "rootcause" / f).exists(), f
    assert (docs / "02_root_cause_report.md").exists()
    assert (docs / "01_dq_scorecard.md").exists() and (docs / "CLEANING.md").exists()
    assert (docs / "stakeholder_memos" / "00_finance_flash.md").exists()
    sc = pd.read_csv(gold / "dq_scorecard.csv")
    assert {
        "rule_id",
        "table",
        "check_type",
        "severity",
        "stakeholder",
        "rows_checked",
        "rows_failed",
        "pct_failed",
        "impact_statement",
        "first_seen",
        "last_seen",
        "run_ts",
        "git_sha",
    } <= set(sc.columns)
    assert sc.loc[sc.rule_id == "C01", "rows_failed"].item() == 90
    silver = ingest.load_layer("silver")
    flags = silver["Insurance_Claims"]["_dq_flags"].fillna("")
    assert flags.str.contains("A02").sum() == 250  # every claim points at the wrong bill
    assert flags.str.contains("C01").sum() == 90
    assert "_cleaned_cols" in silver["Patients"].columns
    # running again appends a new history block rather than overwriting
    n1 = len(pd.read_csv(gold / "dq_history.csv"))
    cli.main(["dq"])
    assert len(pd.read_csv(gold / "dq_history.csv")) == 2 * n1
    # a second run has a previous scorecard to compare with
    assert cli.main(["alerts"]) == 0
    assert (gold / "dq_scorecard_previous.csv").exists()
    again = json.loads((out / "alerts.json").read_text())
    assert again["previous_run_available"] and again["counts"] == {"threshold": 5}  # same data: no drift


def test_at_least_forty_additional_issues_beyond_the_three_confirmed(raw_results):
    res, _, _ = raw_results
    extra = res[(res.rows_failed > 0) & ~res.index.isin(["C01", "C02", "C03"]) & (res.severity != "Info")]
    assert len(extra) >= 40


def test_cleaning_is_idempotent(cleaned):
    silver, _ = cleaned
    again, changes = standardise.standardise(silver)
    assert changes[~changes["rule"].isin(["bmi_recomputed"])].empty, changes.groupby("rule").size().to_dict()


def test_config_as_of_date_is_fixed():
    assert config.as_of_date().isoformat() == "2026-10-21"
