"""Data-validation tests: every hand-written rule must catch a planted defect and pass clean data.

Each case supplies the smallest tables the rule touches, with exactly `failed` bad records among `checked` in-scope records.
"""

import pytest

from conftest import frame
from hcls.dq import runner
from hcls.dq.rules import DATE_COL, load_registry

REGISTRY = {r.id: r for r in load_registry()}


def mk(table, rows):
    rows = [dict(r) for r in rows]
    col = DATE_COL.get(table)
    if col:
        for r in rows:
            r.setdefault(col, "2024-01-01")
    return frame(rows)


# rule_id: ({table: [rows]}, rows_failed, rows_checked)
CASES = {
    "C01": (
        {
            "Insurance_Claims": [
                {"approved_amount": None},
                {"approved_amount": "10"},
                {"approved_amount": "N/A"},
            ]
        },
        2,
        3,
    ),
    "C02": ({"Visits": [{"appointment_id": None}, {"appointment_id": "5"}, {"appointment_id": None}]}, 2, 3),
    "C03": (
        {
            "Medical_Records": [
                {"prescribed_meds": "None"},
                {"prescribed_meds": "Aspirin"},
                {"prescribed_meds": None},
                {"prescribed_meds": "none"},
            ]
        },
        3,
        4,
    ),
    "A01": (
        {
            "Insurance_Claims": [
                {"billing_id": "1"},
                {"billing_id": "1"},
                {"billing_id": "2"},
                {"billing_id": None},
            ]
        },
        1,
        3,
    ),
    "A02": (
        {
            "Insurance_Claims": [
                {"billing_id": "1", "patient_id": "10"},
                {"billing_id": "2", "patient_id": "20"},
                {"billing_id": "9", "patient_id": "5"},
            ],
            "Billing": [{"billing_id": "1", "patient_id": "99"}, {"billing_id": "2", "patient_id": "20"}],
        },
        1,
        2,
    ),
    "A03": (
        {
            "Insurance_Claims": [
                {"billing_id": "1", "submitted_amount": "500"},
                {"billing_id": "2", "submitted_amount": "50"},
            ],
            "Billing": [
                {"billing_id": "1", "total_amount": "100"},
                {"billing_id": "2", "total_amount": "100"},
            ],
        },
        1,
        2,
    ),
    "A04": (
        {
            "Insurance_Claims": [
                {"submitted_date": "2024-02-01", "approved_date": "2024-01-01"},
                {"submitted_date": "2024-01-01", "approved_date": "2024-02-01"},
                {"submitted_date": "2024-01-01", "approved_date": None},
            ]
        },
        1,
        2,
    ),
    "A05": (
        {
            "Insurance_Claims": [
                {"submitted_date": "2024-02-01", "paid_date": "2024-01-01"},
                {"submitted_date": "2024-01-01", "paid_date": "2024-02-01"},
                {"submitted_date": "2024-01-01", "paid_date": None},
            ]
        },
        1,
        2,
    ),
    "A45": (
        {
            "Insurance_Claims": [
                {"approved_date": "2024-02-01", "paid_date": "2024-01-01"},
                {"approved_date": "2024-01-01", "paid_date": "2024-02-01"},
                {"approved_date": None, "paid_date": "2024-02-01"},
            ]
        },
        1,
        2,
    ),
    "A07": (
        {
            "Insurance_Claims": [
                {"submitted_amount": "-5"},
                {"submitted_amount": "10"},
                {"submitted_amount": None},
            ]
        },
        1,
        2,
    ),
    "A08": (
        {
            "Insurance_Claims": [
                {"claim_status": "Denied", "denial_reason": None},
                {"claim_status": "Denied", "denial_reason": "Coding error"},
                {"claim_status": "Approved", "denial_reason": None},
            ]
        },
        1,
        2,
    ),
    "A44": (
        {
            "Insurance_Claims": [
                {"approved_amount": "200", "submitted_amount": "100"},
                {"approved_amount": "50", "submitted_amount": "100"},
                {"approved_amount": None, "submitted_amount": "100"},
            ]
        },
        1,
        2,
    ),
    "A09": (
        {
            "Billing": [
                {"insurance_covered": "60", "patient_responsibility": "40", "total_amount": "100"},
                {"insurance_covered": "60", "patient_responsibility": "30", "total_amount": "100"},
            ]
        },
        1,
        2,
    ),
    "A10": (
        {
            "Billing": [
                {"amount_paid": "120", "patient_responsibility": "100"},
                {"amount_paid": "100", "patient_responsibility": "100"},
            ]
        },
        1,
        2,
    ),
    "A11": ({"Billing": [{"total_amount": "-5"}, {"total_amount": "5"}]}, 1, 2),
    "A12": (
        {
            "Billing": [{"appointment_id": "1"}, {"appointment_id": "2"}, {"appointment_id": "3"}],
            "Appointments": [
                {"appointment_id": "1", "status": "Cancelled"},
                {"appointment_id": "2", "status": "Completed"},
            ],
        },
        1,
        2,
    ),
    "A13": (
        {
            "Billing": [
                {"billing_date": "2024-03-01", "due_date": "2024-02-01"},
                {"billing_date": "2024-01-01", "due_date": "2024-02-01"},
            ]
        },
        1,
        2,
    ),
    "A16": (
        {"Patients": [{"patient_id": "1"}, {"patient_id": "1"}, {"patient_id": "2"}, {"patient_id": None}]},
        1,
        3,
    ),
    "A17": (
        {
            "Patients": [
                {"email": "a@x.com"},
                {"email": "A@x.com"},
                {"email": "b@x.com"},
                {"email": "not-an-email"},
            ]
        },
        1,
        3,
    ),
    "A49": (
        {
            "Patients": [
                {"height_cm": "170", "weight_kg": "70", "bmi": "24.2"},
                {"height_cm": "170", "weight_kg": "70", "bmi": "40"},
                {"height_cm": "170", "weight_kg": "70", "bmi": "x"},
            ]
        },
        1,
        2,
    ),
    "A53": (
        {
            "Patients": [
                {"last_visit_date": "2020-01-01", "registration_date": "2021-01-01"},
                {"last_visit_date": "2022-01-01", "registration_date": "2021-01-01"},
            ]
        },
        1,
        2,
    ),
    "A24": (
        {
            "Admissions": [
                {"admit_date": "2024-02-01", "discharge_date": "2024-01-01"},
                {"admit_date": "2024-01-01", "discharge_date": "2024-02-01"},
                {"admit_date": "2024-01-01", "discharge_date": None},
            ]
        },
        1,
        2,
    ),
    "A25": (
        {
            "Appointments": [
                {"created_at": "2024-02-01T10:00:00", "updated_at": "2024-01-01T10:00:00"},
                {"created_at": "2024-01-01T10:00:00", "updated_at": "2024-02-01T10:00:00"},
                {"created_at": "2024-01-01T10:00:00", "updated_at": None},
            ]
        },
        1,
        2,
    ),
    "A28": (
        {
            "Prescriptions": [
                {"start_date": "2024-02-01", "end_date": "2024-01-01"},
                {"start_date": "2024-01-01", "end_date": "2024-02-01"},
                {"start_date": "2024-01-01", "end_date": None},
            ]
        },
        1,
        2,
    ),
    "A29": (
        {
            "Prescriptions": [
                {"is_active": "True", "end_date": "2020-01-01"},
                {"is_active": "True", "end_date": "2030-01-01"},
                {"is_active": "False", "end_date": "2020-01-01"},
            ]
        },
        1,
        2,
    ),
    "A30": (
        {
            "Prescription_Administration": [
                {"prescription_id": "1", "patient_id": "5"},
                {"prescription_id": "2", "patient_id": "6"},
            ],
            "Prescriptions": [
                {"prescription_id": "1", "patient_id": "9"},
                {"prescription_id": "2", "patient_id": "6"},
            ],
        },
        1,
        2,
    ),
    "A31": (
        {
            "Prescription_Administration": [
                {"prescription_id": "1", "dosage_unit": "mg"},
                {"prescription_id": "2", "dosage_unit": "mL"},
            ],
            "Prescriptions": [
                {"prescription_id": "1", "dosage_unit": "mL"},
                {"prescription_id": "2", "dosage_unit": "mL"},
            ],
        },
        1,
        2,
    ),
    "A32": (
        {
            "Prescription_Administration": [
                {"prescription_id": "1", "administered_datetime": "2023-01-01"},
                {"prescription_id": "2", "administered_datetime": "2024-06-01"},
            ],
            "Prescriptions": [
                {"prescription_id": "1", "start_date": "2024-01-01"},
                {"prescription_id": "2", "start_date": "2024-01-01"},
            ],
        },
        1,
        2,
    ),
    "A34": (
        {
            "Referrals": [
                {"referring_doctor_id": "1", "referred_doctor_id": "1"},
                {"referring_doctor_id": "1", "referred_doctor_id": "2"},
            ]
        },
        1,
        2,
    ),
    "A36": ({"Hierarchy": [{"entity_id": "HD-1"}, {"entity_id": "5"}, {"entity_id": None}]}, 1, 2),
    "A37": (
        {
            "Patient_Insurance": [
                {"coverage_start": "2024-02-01", "coverage_end": "2024-01-01"},
                {"coverage_start": "2024-01-01", "coverage_end": "2024-02-01"},
            ]
        },
        1,
        2,
    ),
    "A38": (
        {
            "Patient_Insurance": [
                {"claim_id": "1", "patient_id": "5"},
                {"claim_id": "2", "patient_id": "6"},
                {"claim_id": None, "patient_id": "7"},
            ],
            "Insurance_Claims": [{"claim_id": "1", "patient_id": "9"}, {"claim_id": "2", "patient_id": "6"}],
        },
        1,
        2,
    ),
    "A39": (
        {
            "Nurses": [
                {"nurse_id": "1", "supervisor_nurse_id": "1"},
                {"nurse_id": "2", "supervisor_nurse_id": "1"},
                {"nurse_id": "3", "supervisor_nurse_id": None},
            ]
        },
        1,
        2,
    ),
    "A40": (
        {
            "Nurse_Assignments": [
                {"nurse_id": "1", "shift_date": "2024-01-01"},
                {"nurse_id": "1", "shift_date": "2024-01-01"},
                {"nurse_id": "1", "shift_date": "2024-01-02"},
            ]
        },
        1,
        3,
    ),
    "A41": (
        {
            "Visits": [
                {"systolic_bp": "80", "diastolic_bp": "120"},
                {"systolic_bp": "120", "diastolic_bp": "80"},
            ]
        },
        1,
        2,
    ),
    "A43a": (
        {"Hospitals": [{"phone_number": "(1) 1"}, {"phone_number": "(1) 1"}, {"phone_number": "(2) 2"}]},
        1,
        3,
    ),
    "A43b": (
        {"Departments": [{"phone_extension": "2500"}, {"phone_extension": "2500"}, {"phone_extension": "1"}]},
        1,
        3,
    ),
    "A43c": (
        {"Doctors": [{"license_number": "MD-1"}, {"license_number": "MD-1"}, {"license_number": "MD-2"}]},
        1,
        3,
    ),
    "A33": (
        {
            "Procedure_Codes": [
                {"code_id": "1", "parent_code_id": None},
                {"code_id": "2", "parent_code_id": "3"},
                {"code_id": "3", "parent_code_id": "2"},
                {"code_id": "4", "parent_code_id": "1"},
                {"code_id": "5", "parent_code_id": "2"},
            ]
        },
        3,
        5,
    ),
}


def test_every_registry_rule_has_a_data_test():
    assert set(CASES) == set(REGISTRY)


def test_registry_sql_files_exist_and_ids_unique():
    ids = [r.id for r in load_registry()]
    assert len(ids) == len(set(ids))
    assert all(r.sql or r.python_fn for r in REGISTRY.values())


@pytest.mark.parametrize("rule_id", sorted(CASES))
def test_rule_catches_defect_and_passes_clean_rows(rule_id):
    tables, failed, checked = CASES[rule_id]
    frames = {t: mk(t, rows) for t, rows in tables.items()}
    res, _, fails = runner.run_rules(frames, rules=[REGISTRY[rule_id]])
    row = res.iloc[0]
    assert (int(row["rows_failed"]), int(row["rows_checked"])) == (failed, checked)
    assert len(fails) == failed
