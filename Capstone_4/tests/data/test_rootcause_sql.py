"""Planted-defect tests for the root-cause SQL: each evidence query must detect a defect we put there on purpose."""

import pandas as pd
import pytest

from hcls.dq.runner import connect
from hcls.rootcause import evidence


def t(**cols):
    n = len(next(iter(cols.values())))
    df = pd.DataFrame(cols)
    df.insert(0, "_row_num", range(2, n + 2))
    return df


def run(name, frames):
    con = connect(frames)
    try:
        return evidence.run_sql(name, con)
    finally:
        con.close()


def test_c01_blank_by_status_separates_open_from_decided():
    claims = t(
        claim_id=["1", "2", "3", "4"],
        claim_status=["Approved", "Approved", "Pending", "Pending"],
        approved_amount=["100", "200", "", ""],
        approved_date=["2024-01-01", "2024-01-02", "", ""],
        paid_date=["2024-02-01", "", "", ""],
    )
    out = run("c01_blank_by_status", {"Insurance_Claims": claims}).set_index("claim_status")
    assert out.loc["Approved", "approved_amount_blank"] == 0
    assert out.loc["Pending", ["claims", "approved_amount_blank", "approved_date_blank"]].tolist() == [
        2,
        2,
        2,
    ]


def test_link_health_counts_same_patient_matches():
    appts = t(
        appointment_id=["1", "2"], patient_id=["10", "20"], appointment_date=["2024-01-01", "2024-01-02"]
    )
    visits = t(
        visit_id=["1", "2", "3"],
        appointment_id=["1", "2", ""],
        patient_id=["10", "99", "10"],
        visit_date=["2024-01-01", "2024-01-05", "2024-01-06"],
    )
    frames = {
        "Appointments": appts,
        "Visits": visits,
        "Medical_Records": t(appointment_id=[""], patient_id=[""], record_date=[""]),
        "Billing": t(appointment_id=[""], patient_id=[""], billing_date=[""], billing_id=[""]),
        "Insurance_Claims": t(billing_id=[""], patient_id=[""], submitted_date=[""], claim_id=[""]),
        "Patient_Insurance": t(claim_id=[""], patient_id=[""]),
        "Prescription_Administration": t(prescription_id=[""], patient_id=[""], administered_datetime=[""]),
        "Prescriptions": t(prescription_id=[""], patient_id=[""], start_date=[""]),
    }
    out = run("link_health", frames).set_index("link").loc["Visits -> Appointments"]
    assert (out.linked_rows, out.same_patient) == (
        2,
        1,
    )  # visit 3 has no link; visit 2 points at someone else's appointment


def test_claim_bill_amounts_flags_wildly_different_pairs():
    claims = t(
        claim_id=["1", "2"], billing_id=["1", "2"], patient_id=["1", "2"], submitted_amount=["1000", "100"]
    )
    bills = t(billing_id=["1", "2"], patient_id=["1", "2"], total_amount=["10", "100"])
    out = run("claim_bill_amounts", {"Insurance_Claims": claims, "Billing": bills}).iloc[0]
    assert out.pairs == 2 and out.within_25_percent == 1 and out.median_ratio > 1


def test_sentinel_ids_are_grouped_by_kind():
    pats = t(patient_id=["1", "2"])
    appts = t(appointment_id=["1", "2", "3", "4"], patient_id=["1", "-1", "88888", "99991"])
    names = (
        "Visits",
        "Medical_Records",
        "Billing",
        "Prescriptions",
        "Prescription_Administration",
        "Admissions",
        "Referrals",
    )
    frames = {n: t(patient_id=["1"]) for n in names}
    frames.update({"Patients": pats, "Appointments": appts})
    out = run("sentinel_ids", frames)
    got = out[out["table_name"] == "Appointments"]
    assert int(got["rows_affected"].sum()) == 3


@pytest.mark.parametrize("name", evidence.EVIDENCE_SQL)
def test_every_evidence_query_exists_and_is_registered(name):
    from hcls import config

    assert (config.project_root() / "sql" / "rootcause" / f"{name}.sql").exists()
