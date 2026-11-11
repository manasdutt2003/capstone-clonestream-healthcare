"""Validators reject planted bad rows and pass clean rows; real-data counts match the data-quality scorecard."""

import pandas as pd
import pytest

from hcls.remediation import validators as V


def frame(**cols):
    n = len(next(iter(cols.values())))
    df = pd.DataFrame(cols)
    df.insert(0, "_row_num", range(2, n + 2))
    return df


def rejected(check_id, table, df, ctx=None):
    v = V.validate_table(table, df, ctx or {})
    return sorted(v.loc[v["check_id"] == check_id, "row_num"].tolist())


PATIENTS = frame(patient_id=["1", "2", "3"])


def test_every_check_names_the_issue_it_prevents_and_has_a_unique_id():
    ids = [c.id for c in V.CHECKS]
    assert len(ids) == len(set(ids)) and len(ids) >= 40
    assert all(c.issue and c.description and c.kind for c in V.CHECKS)
    assert {c.kind for c in V.CHECKS} >= {
        "not_null", "foreign_key", "same_patient", "sentinel", "unique", "range", "date_order", "enum", "business",
    }  # fmt: skip


def test_not_null_checks_for_the_three_confirmed_issues():
    claims = frame(
        claim_status=["Approved", "Approved", "Pending", "Denied"], approved_amount=["10", "", "", ""]
    )
    assert rejected("V-C01", "Insurance_Claims", claims) == [
        3,
        5,
    ]  # blank only matters once the claim is decided
    assert rejected("V-C02", "Visits", frame(appointment_id=["1", "", None])) == [3, 4]
    assert rejected("V-C03", "Medical_Records", frame(prescribed_meds=["Insulin", None, ""])) == [3, 4]


def test_foreign_key_and_placeholder_ids():
    visits = frame(patient_id=["1", "9", "-1", "88888", "99991", "3"])
    assert rejected("V-FK-Visits-patient_id", "Visits", visits, {"Patients": PATIENTS}) == [3, 4, 5, 6]
    assert rejected("V-SENT-Visits", "Visits", visits) == [4, 5, 6]
    assert (
        rejected("V-FK-Visits-patient_id", "Visits", visits) == []
    )  # no parent table supplied: skipped, not guessed


def test_same_patient_link_rejects_a_claim_pointing_at_someone_elses_bill():
    bills = frame(billing_id=["10", "11"], patient_id=["1", "2"])
    claims = frame(billing_id=["10", "10", "11", "99", ""], patient_id=["1", "2", "2", "1", "1"])
    got = rejected("V-LINK-Insurance_Claims-billing_id", "Insurance_Claims", claims, {"Billing": bills})
    assert got == [
        3
    ]  # row 3: bill 10 belongs to patient 1, claim says patient 2 (99 and blank are FK / not-null matters)


def test_unique_rejects_the_second_and_later_rows_only():
    assert rejected("V-A01", "Insurance_Claims", frame(billing_id=["5", "6", "5", "5", ""])) == [4, 5]
    assert rejected("V-A16", "Patients", frame(patient_id=["1", "1", "2"])) == [3]


def test_range_checks():
    claims = frame(submitted_amount=["100", "-5", "50"], approved_amount=["80", "1", "70"])
    assert rejected("V-A07", "Insurance_Claims", claims) == [3]
    assert rejected("V-A44", "Insurance_Claims", claims) == [
        3,
        4,
    ]  # 1 > -5 and 70 > 50 are both "approved above submitted"
    bills = frame(
        total_amount=["100", "-1", "100"], insurance_covered=["60", "-1", "60"],
        patient_responsibility=["40", "0", "30"], amount_paid=["40", "0", "35"],
    )  # fmt: skip
    assert rejected("V-A11", "Billing", bills) == [3]
    assert rejected("V-A09", "Billing", bills) == [4]
    assert rejected("V-A10", "Billing", bills) == [4]


def test_date_order_and_future_dates():
    adm = frame(admit_date=["2024-01-05", "2024-01-05"], discharge_date=["2024-01-06", "2024-01-01"])
    assert rejected("V-A24", "Admissions", adm) == [3]
    rx = frame(start_date=["2024-02-01", ""], end_date=["2024-01-01", "2024-01-01"])
    assert rejected("V-A28", "Prescriptions", rx) == [2]
    claims = frame(
        submitted_date=["2024-01-01", "2024-01-01", "2027-01-01"],
        approved_date=["2023-12-01", "2024-02-01", ""],
        paid_date=["", "2024-01-15", "2028-01-01"],
    )
    assert rejected("V-DO-claims-approved", "Insurance_Claims", claims) == [2]
    assert rejected("V-DO-claims-paid", "Insurance_Claims", claims) == [3]
    assert rejected("V-FUT-claims-submitted", "Insurance_Claims", claims) == [4]
    assert rejected("V-FUT-claims-paid", "Insurance_Claims", claims) == [4]


def test_enum_and_cancelled_appointment_bill():
    assert rejected(
        "V-ENUM-claim_status", "Insurance_Claims", frame(claim_status=["Approved", "Maybe", ""])
    ) == [3]
    appts = frame(appointment_id=["1", "2", "3"], status=["Completed", "Cancelled", "No-Show"])
    bills = frame(appointment_id=["1", "2", "3", "9"])
    assert rejected("V-A12", "Billing", bills, {"Appointments": appts}) == [3, 4]


def test_clean_rows_pass_every_check():
    ctx = {
        "Patients": PATIENTS,
        "Appointments": frame(appointment_id=["1"], status=["Completed"], patient_id=["1"]),
        "Billing": frame(billing_id=["10"], patient_id=["1"], appointment_id=["1"]),
    }
    claims = frame(
        claim_status=["Approved"], billing_id=["10"], patient_id=["1"], claim_id=["1"],
        submitted_amount=["100"], approved_amount=["80"], submitted_date=["2024-01-01"],
        approved_date=["2024-02-01"], paid_date=["2024-03-01"],
    )  # fmt: skip
    assert V.validate_table("Insurance_Claims", claims, ctx).empty


def test_catch_report_counts_rows_per_check():
    frames = {
        "Visits": frame(appointment_id=["1", "", ""], patient_id=["1", "2", "3"], visit_id=["1", "2", "3"])
    }
    rep = V.catch_report(frames).set_index("check_id")
    assert rep.loc["V-C02", "rows_it_would_reject"] == 2 and rep.loc["V-C02", "rows_in_table"] == 3
    assert rep.loc["V-C03", "rows_in_table"] == 0


@pytest.mark.realdata
def test_validators_catch_what_the_scorecard_reports(cleaned):
    silver = cleaned[0]
    rep = V.catch_report(silver).set_index("check_id")["rows_it_would_reject"]
    assert rep["V-C02"] == 123 and rep["V-C03"] == 40 and rep["V-C01"] == 0
    assert (
        rep["V-LINK-Insurance_Claims-billing_id"],
        rep["V-LINK-Prescription_Administration-prescription_id"],
    ) == (250, 400)
    assert rep["V-LINK-Patient_Insurance-claim_id"] == 230
    assert (rep["V-A24"], rep["V-A12"], rep["V-A01"], rep["V-A16"]) == (152, 81, 89, 55)
    assert (rep["V-A07"], rep["V-A44"], rep["V-A11"], rep["V-A09"], rep["V-A10"]) == (2, 2, 3, 7, 4)
    assert rep["V-FK-Visits-patient_id"] == 45 and rep["V-FK-Appointments-patient_id"] == 12
