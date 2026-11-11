"""Regression: the root-cause conclusions for the real workbook stay pinned (see docs/02_root_cause_report.md)."""

import pytest

from hcls.dq import scorecard
from hcls.rootcause import evidence

pytestmark = pytest.mark.realdata


@pytest.fixture(scope="module")
def ev(bronze, raw_results):
    res, tl, fails = raw_results
    return evidence.collect(bronze, scorecard.build_scorecard(res.reset_index(), tl), fails)


@pytest.fixture(scope="module")
def verdicts(ev):
    return {h["id"]: h["verdict"] for h in evidence.build_hypotheses(ev)}


def test_hypothesis_verdicts_are_pinned(verdicts):
    assert verdicts == {
        "H1.1": "Ruled out",
        "H1.2": "Confirmed",
        "H1.3": "Ruled out",
        "H2.1": "Likely",
        "H2.2": "Not supported",
        "H2.3": "Ruled out",
        "H3.1": "Partly ruled out",
        "H3.2": "Likely",
        "H3.3": "Not feasible",
        "H3.4": "Inconclusive",
        "H4.1": "Ruled out",
        "H4.2": "Ruled out",
        "H4.3": "Confirmed",
        "H4.4": "Confirmed",
    }


def test_critical_failures_are_flat_over_time(ev):
    s = ev["timeline_summary"].set_index("rule_id")
    for rule in ("C01", "C02", "C03"):
        assert s.loc[rule, "verdict"].startswith("flat"), rule
    assert s.loc["C01", "years_with_failures"] == 7 and s.loc["C02", "years_with_failures"] == 7
    for rule in ("A02", "A30"):
        assert s.loc[rule, "overall_rate_pct"] == 100


def test_only_the_billing_to_appointment_link_is_sound(ev):
    lh = ev["link_health"].set_index("link")
    assert (
        lh.loc["Visits -> Appointments", "linked_rows"],
        lh.loc["Visits -> Appointments", "same_patient"],
    ) == (277, 1)
    assert lh.loc["Medical_Records -> Appointments", "same_patient"] == 0
    assert (
        lh.loc["Billing -> Appointments", "same_patient"],
        lh.loc["Billing -> Appointments", "linked_rows"],
    ) == (248, 249)
    for link in (
        "Insurance_Claims -> Billing",
        "Patient_Insurance -> Insurance_Claims",
        "Prescription_Administration -> Prescriptions",
    ):
        assert lh.loc[link, "same_patient"] == 0, link


def test_lineage_edge_counts(ev):
    assert ev["lineage"]["status"].value_counts().to_dict() == {"healthy": 17, "degraded": 12, "broken": 10}


def test_claims_cannot_be_reconciled_to_bills(ev):
    a = ev["claim_bill_amounts"].iloc[0]
    assert a.pairs == 250 and a.within_25_percent == 1 and round(a.median_ratio) == 64
    assert ev["claim_patient_has_bill"].iloc[0].claims_whose_patient_has_a_bill == 9


def test_c03_and_sentinel_numbers(ev):
    plan = ev["c03_by_plan"].set_index("plan_type")
    assert plan.loc["plan names a drug", "meds_none"] == 20
    assert ev["c03_backfill"].iloc[0].patient_has_any_prescription == 3
    assert ev["c03_backfill"].iloc[0].same_patient_and_doctor == 0
    s = ev["sentinel_ids"]
    assert int(s["rows_affected"].sum()) == 116 and s["table_name"].nunique() == 8
    sp = ev["sentinel_propagation"].iloc[0]
    assert (sp.bills_with_orphan_patient, sp.appointment_has_same_orphan_id) == (13, 12)


def test_report_renders_with_every_section(ev, verdicts):
    from hcls import reports

    text = reports.render_root_cause_report(ev, evidence.build_hypotheses(ev), "test")
    for heading in (
        "## 1.",
        "## 2.",
        "## 3.",
        "## 4.",
        "## 5.",
        "## 6.",
        "## 7.",
        "## 8.",
        "## 9.",
        "Appendix A",
        "Appendix B",
    ):
        assert heading in text, heading
    assert "```mermaid" in text and "flowchart LR" in text
    assert all(f"| {hid} |" in text for hid in verdicts)
