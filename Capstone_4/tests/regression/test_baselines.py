"""Regression tests: numbers established by profiling the real workbook (SPEC section 3) stay pinned.

If one of these fails because the DATA or a RULE changed on purpose, update SPEC section 3 and tests/regression/baselines.json
and record the reason in DECISIONS.md. Never edit a baseline just to make a test pass.
"""

import json
from pathlib import Path

import pytest

from hcls import standardise as S
from hcls.dq import scorecard
from hcls.recon import flash

BASE = json.loads((Path(__file__).parent / "baselines.json").read_text())

pytestmark = pytest.mark.realdata


def test_the_three_confirmed_issues_match_the_brief(raw_results):
    res, _, _ = raw_results
    assert (res.loc["C01", "rows_failed"], res.loc["C01", "rows_checked"]) == (90, 250)  # 36% of claims
    assert (res.loc["C02", "rows_failed"], res.loc["C02", "rows_checked"]) == (123, 400)  # 30% of visits
    assert (res.loc["C03", "rows_failed"], res.loc["C03", "rows_checked"]) == (
        40,
        206,
    )  # 19% of medical records


@pytest.mark.parametrize("rule_id", sorted(BASE["raw_rules"]))
def test_pinned_rule_counts(raw_results, rule_id):
    res, _, _ = raw_results
    assert [int(res.loc[rule_id, "rows_failed"]), int(res.loc[rule_id, "rows_checked"])] == BASE["raw_rules"][
        rule_id
    ]


def test_rule_count_and_sheet_row_counts(raw_results, bronze):
    res, _, _ = raw_results
    assert len(res) == BASE["rules_total"]
    assert {k: len(v) for k, v in bronze.items()} == BASE["sheet_rows"]


def test_join_keys_are_unique_so_join_rules_do_not_fan_out(bronze):
    for table, key in (
        ("Billing", "billing_id"),
        ("Prescriptions", "prescription_id"),
        ("Insurance_Claims", "claim_id"),
        ("Appointments", "appointment_id"),
    ):
        ids = bronze[table][key]
        assert ids.is_unique, f"{table}.{key} must be unique for the join rules to be valid"


def test_confirmed_issues_are_spread_over_many_years_not_a_recent_break(raw_results):
    _, tl, _ = raw_results
    for rule, min_years in (("C01", 6), ("C02", 6)):
        years = tl[(tl.rule_id == rule) & (tl.rows_failed > 0)].year.nunique()
        assert years >= min_years


def test_all_blank_approved_amounts_are_unadjudicated_claims(bronze):
    claims = bronze["Insurance_Claims"]
    blank = claims[claims["approved_amount"].isna()]
    assert set(blank["claim_status"]) == {"Submitted", "Pending", "In Review"} and len(blank) == 90


def test_finance_flash_numbers(cleaned):
    silver, _ = cleaned
    t = flash.flash_tables(silver["Insurance_Claims"])
    assert round(t["approved_submitted"], 2) == 2604465.33
    assert round(t["approved_paid"], 2) == 2025699.01
    assert round(t["gap"], 2) == 578766.32
    assert round(t["pipeline_submitted"], 2) == 2225289.25
    assert round(t["total_submitted"], 2) == 6066812.08
    assert t["claims_total"] == 250 and t["blank_approved"] == 90 and t["blank_in_pipeline"] == 90
    assert round(t["pipeline_expected"]) == 1730784
    # every claim dollar sits in exactly one status bucket
    parts = t["approved_submitted"] + t["pipeline_submitted"] + t["denied"] + t["appealed"]
    assert round(parts, 2) == round(t["total_submitted"], 2)


def test_workbook_referential_integrity_sheet_over_reports_two_lines(bronze):
    ri = scorecard.ri_crosscheck(bronze).set_index(["table", "fk_column"])
    pcp = ri.loc[("Patients", "primary_care_doctor_id")]
    assert (pcp.sheet_violation_types, pcp.engine_violation_types, pcp.verdict) == (
        500,
        0,
        "sheet over-reports",
    )
    hosp = ri.loc[("Patients", "hospital_id")]
    assert (hosp.sheet_violation_types, hosp.engine_violation_types, hosp.engine_violating_rows) == (
        31,
        6,
        81,
    )
    assert (ri["verdict"] != "matches").sum() == 2


def test_cleaning_totals_are_pinned(cleaned):
    _, changes = cleaned
    assert len(changes) == BASE["cleaning"]["total_cells_changed"]
    by_rule = S.cleaning_summary(changes).groupby("rule").cells_changed.sum().to_dict()
    assert {k: int(v) for k, v in by_rule.items()} == BASE["cleaning"]["by_rule"]


def test_cleaning_never_changes_the_confirmed_issue_counts(raw_results, clean_results):
    res, _, _ = raw_results
    for rule in ("C01", "C02", "C03", "A02", "A30"):
        assert clean_results.loc[rule, "rows_failed"] == res.loc[rule, "rows_failed"]


def test_cleaning_fixes_every_format_rule(clean_results):
    for rule in BASE["clean_rules_zero"]:
        assert clean_results.loc[rule, "rows_failed"] == 0, rule
