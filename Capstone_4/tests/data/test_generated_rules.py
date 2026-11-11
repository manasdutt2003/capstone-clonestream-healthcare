"""Data-validation tests for the generated rule families (null, FK, date, format, domain, bounds)."""

import pytest

from conftest import frame
from hcls.dq import runner
from hcls.dq.rules import DATE_COL, SPIKE_MIN, build_rules, generated_rules


def run_one(rule_id, tables):
    cols = {t: [c for c in df.columns if not c.startswith("_")] for t, df in tables.items()}
    rule = next(r for r in generated_rules(cols) if r.id == rule_id)
    res, _, _ = runner.run_rules(tables, rules=[rule])
    row = res.iloc[0]
    return int(row["rows_failed"]), int(row["rows_checked"])


def col(table, name, values):
    """One-column table. The table's timeline date column is filled with a neutral date when it is not the column under test."""
    rows = [{name: v} for v in values]
    date_col = DATE_COL.get(table)
    if date_col and date_col != name:
        for r in rows:
            r[date_col] = "2024-01-01"
    return {table: frame(rows)}


@pytest.mark.parametrize(
    "rule_id, table, column, values, expected",
    [
        # completeness: NULL and placeholder text are missing, the answer 'None' is not
        (
            "N-Patients-employer_name",
            "Patients",
            "employer_name",
            [None, "N/A", "Acme", "None", "UNKNOWN"],
            (3, 5),
        ),
        # dates
        (
            "F-Patients-date_of_birth",
            "Patients",
            "date_of_birth",
            ["1990-01-01", "01/15/1987", "not available", "2025-13-01"],
            (3, 4),
        ),
        (
            "F-Appointments-created_at",
            "Appointments",
            "created_at",
            ["2024-01-01T10:00:00", "garbage"],
            (1, 2),
        ),
        (
            "S-Patients-date_of_birth",
            "Patients",
            "date_of_birth",
            ["1800-01-01", "1990-01-01", "1900-01-01"],
            (2, 3),
        ),
        (
            "T-Patients-date_of_birth",
            "Patients",
            "date_of_birth",
            ["2030-01-01", "2020-01-01", "bad"],
            (1, 2),
        ),
        ("F-Admissions-admit_time", "Admissions", "admit_time", ["08:30", "25:99"], (1, 2)),
        # formats
        (
            "F-Patients-phone_number",
            "Patients",
            "phone_number",
            ["(123) 456-7890", "1234567890", "12345"],
            (2, 3),
        ),
        ("F-Patients-email", "Patients", "email", ["a@b.com", "not-an-email", "user@.com"], (2, 3)),
        (
            "F-Patients-insurance_policy_number",
            "Patients",
            "insurance_policy_number",
            ["POL-123456", "POL-ABC"],
            (1, 2),
        ),
        (
            "F-Patients-insurance_group_number",
            "Patients",
            "insurance_group_number",
            ["GRP-1234", "G1234"],
            (1, 2),
        ),
        (
            "F-Medical_Records-diagnosis_code",
            "Medical_Records",
            "diagnosis_code",
            ["E11.9", "Z23", "INVALID-CODE"],
            (1, 3),
        ),
        (
            "J-Medical_Records-radiology_report",
            "Medical_Records",
            "radiology_report",
            ['{"a": 1}', "not json"],
            (1, 2),
        ),
        # domains
        ("V-Patients-gender", "Patients", "gender", ["Male", "F", "Mle", "Female"], (2, 4)),
        ("V-Patients-blood_type", "Patients", "blood_type", ["O+", "o+", "AB"], (2, 3)),
        ("V-Hospitals-city", "Hospitals", "city", ["Boston", "Philly", "SF"], (2, 3)),
        # numeric bounds: cleaned (B) and flag-only (X)
        ("B-Patients-height_cm", "Patients", "height_cm", ["170", "-10", "tall", "9999", "180"], (3, 5)),
        ("B-Doctors-rating", "Doctors", "rating", ["4.5", "10", "0"], (1, 3)),
        ("X-Visits-heart_rate", "Visits", "heart_rate", ["70", "0", "300"], (2, 3)),
    ],
)
def test_generated_rule(rule_id, table, column, values, expected):
    assert run_one(rule_id, col(table, column, values)) == expected


def test_spike_rule_flags_a_default_date():
    values = ["2020-01-01"] * SPIKE_MIN + ["2021-05-05", "2022-06-06"]
    assert run_one("P-Patients-registration_date", col("Patients", "registration_date", values)) == (
        SPIKE_MIN,
        SPIKE_MIN + 2,
    )


def test_foreign_key_rule_counts_orphans_and_unparseable_ids():
    tables = {
        "Visits": frame(
            [
                {"patient_id": "1", "visit_date": "2024-01-01"},
                {"patient_id": "99", "visit_date": "2024-01-01"},
                {"patient_id": "2027-07-30", "visit_date": "2024-01-01"},
                {"patient_id": None, "visit_date": "2024-01-01"},
            ]
        ),
        "Patients": frame([{"patient_id": "1"}, {"patient_id": "2"}]),
    }
    assert run_one("R-Visits-patient_id", tables) == (2, 3)


def test_rule_ids_are_unique_and_cover_every_column():
    cols = {"Patients": ["patient_id", "gender"], "Visits": ["visit_id", "appointment_id", "visit_date"]}
    rules = build_rules(cols)
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids))
    assert "N-Patients-patient_id" in ids and "N-Visits-visit_id" in ids
    assert "N-Visits-appointment_id" not in ids  # replaced by hand-written C02
