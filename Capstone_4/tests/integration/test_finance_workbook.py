"""Integration + regression tests for the finance workbook, brief and the real-data reconciliation numbers."""

import openpyxl
import pandas as pd
import pytest

from hcls import cli
from hcls.recon import claims as C
from hcls.recon import excel_export

pytestmark = pytest.mark.realdata


@pytest.fixture(scope="module")
def detail(cleaned):
    return C.classify(cleaned[0]["Insurance_Claims"])


@pytest.fixture(scope="module")
def workbook(detail, bronze, tmp_path_factory):
    path = tmp_path_factory.mktemp("fin") / "recon.xlsx"
    excel_export.write_finance_workbook(
        detail, C.overcharge_evidence(bronze), path, run_ts="2026-10-21T00:00:00Z"
    )
    return path


# ------------------------------------------------------------------ pinned real-data numbers


def test_buckets_tie_to_total_submitted(detail):
    t = C.tie_out(detail)
    assert t["ties"] and t["total_submitted"] == 6066812.08 and t["claims_total"] == 250


def test_bucket_amounts_are_pinned(detail):
    s = C.bucket_summary(detail).set_index("bucket")
    assert s.loc["Paid", ["claims", "amount"]].tolist() == [97, 1945489.16]
    assert s.loc["Adjustment", "amount"] == 636901.00
    assert s.loc["Denied", ["claims", "amount"]].tolist() == [49, 1123430.56]
    assert s.loc["Under appeal", ["claims", "amount"]].tolist() == [10, 157484.18]
    assert s.loc["Pipeline", ["claims", "amount"]].tolist() == [90, 2225289.25]
    assert s.loc["DQ Hold", "claims"] == 4 and s.loc["Approved, not yet paid", "claims"] == 0


def test_held_claims_explain_the_difference_from_the_flash(detail):
    # as recorded (Flash): approved 2,025,699.01 and gap 578,766.32 on 100 approved claims
    appr = detail[detail["claim_status"] == "Approved"]
    assert round(appr["approved_amount"].sum(), 2) == 2025699.01
    assert round(appr["submitted_amount"].sum() - appr["approved_amount"].sum(), 2) == 578766.32
    held = detail[(detail["bucket"] == "DQ Hold") & (detail["claim_status"] == "Approved")]
    assert len(held) == 3 and round(held["approved_amount"].sum(), 2) == 80209.85
    assert round(2025699.01 - held["approved_amount"].sum(), 2) == 1945489.16


def test_expected_value_is_below_the_no_denial_ceiling(detail):
    ev = C.expected_value(detail)
    assert ev["expected"] == pytest.approx(1168236.79, abs=1)
    assert ev["low"] == pytest.approx(1038842.45, rel=0.02) and ev["high"] == pytest.approx(
        1297259.94, rel=0.02
    )
    assert (
        ev["ceiling_no_denials"] == pytest.approx(1676460.89, abs=1) and ev["high"] < ev["ceiling_no_denials"]
    )


def test_pipeline_is_mostly_old_and_dates_are_unreliable(detail):
    aging = C.pipeline_aging(detail).set_index("age")
    assert aging.loc["Over 1 year", "claims"] == 78 and aging["claims"].sum() == 90
    x = C.date_flag_effect(detail)
    assert (x["paid_claims"], x["paid_claims_with_date_flag"]) == (97, 84)


def test_overcharge_evidence_matches_the_root_cause_report(bronze):
    e = C.overcharge_evidence(bronze)
    assert (e["same_patient"], e["linked_claims"]) == (0, 250)
    assert round(e["median_ratio"]) == 64 and e["claims_whose_patient_has_a_bill"] == 9


# ------------------------------------------------------------------ workbook structure


def test_workbook_has_the_four_sheets_in_order(workbook):
    assert openpyxl.load_workbook(workbook).sheetnames == [
        "Claims Summary",
        "Customer Detail",
        "DQ Exceptions",
        "Read Me",
    ]


def test_customer_detail_has_one_row_per_claim_with_formats(workbook, detail):
    wb = openpyxl.load_workbook(workbook)
    ws = wb["Customer Detail"]
    header = [c.value for c in ws[1]]
    for col in (
        "Claim ID",
        "Claim number",
        "Patient ID",
        "Status",
        "Submitted",
        "Approved",
        "Bucket",
        "Confidence",
        "DQ flags",
    ):
        assert col in header, col
    assert ws.max_row == 251 and ws.freeze_panes == "A2" and ws.auto_filter.ref.startswith("A1:")
    assert ws["E2"].number_format.startswith("#,##0.00")
    assert len(ws.conditional_formatting) >= 1  # confidence colours are conditional rules, not painted cells
    df = pd.read_excel(workbook, sheet_name="Customer Detail")
    assert round(df["Submitted"].sum(), 2) == 6066812.08
    assert set(df["Confidence"]) <= set(C.CONFIDENCE.values())


def test_summary_sheet_states_the_tie_out_and_the_overcharge_answer(workbook):
    text = "\n".join(
        str(c.value)
        for row in openpyxl.load_workbook(workbook)["Claims Summary"].iter_rows()
        for c in row
        if c.value is not None
    )
    assert "Ties to the cent" in text and "Not determinable" in text and "$2.3M" in text
    assert "Ceiling if nothing were ever denied" in text and "Assumptions" in text


def test_exceptions_sheet_lists_the_four_holds(workbook):
    df = pd.read_excel(workbook, sheet_name="DQ Exceptions")
    assert (df["Treatment"] == "Held out of all other buckets").sum() == 4


def test_read_me_has_as_of_run_time_and_version(workbook):
    ws = openpyxl.load_workbook(workbook)["Read Me"]
    cells = {ws.cell(row=r, column=1).value: ws.cell(row=r, column=2).value for r in range(1, ws.max_row + 1)}
    assert cells["As-of date"] == "2026-10-21" and cells["Run timestamp (UTC)"] == "2026-10-21T00:00:00Z"
    assert cells["Code version (git commit)"]


# ------------------------------------------------------------------ end to end


def test_recon_command_writes_workbook_brief_and_timing(tmp_outputs):
    assert cli.main(["all"]) == 0
    out = tmp_outputs / "outputs"
    assert (out / "finance" / "CloneStream_Claims_Reconciliation_2026-10-21.xlsx").exists()
    for f in ("recon_claims.csv", "recon_buckets.csv", "recon_exceptions.csv", "recon_timing.csv"):
        assert (out / "gold" / f).exists(), f
    brief = (tmp_outputs / "docs" / "03_finance_brief.md").read_text(encoding="utf-8")
    for needle in ("## The answer", "to the cent", "hold any refund decision", "Reconciling to the brief"):
        assert needle in brief, needle
    timing = pd.read_csv(out / "gold" / "recon_timing.csv").iloc[0]
    assert bool(timing["within_sla"]) and timing["seconds"] < 300
    detail = pd.read_csv(out / "gold" / "recon_claims.csv")
    assert len(detail) == 250 and detail["bucket"].notna().all()
