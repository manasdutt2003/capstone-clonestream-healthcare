import pytest

from hcls import standardise as S


@pytest.mark.parametrize(
    "raw, expected, rule",
    [
        ("2024-03-12", "2024-03-12", None),
        ("2024-03-12T09:00:00", "2024-03-12", "date_trimmed_time"),
        ("01/15/1987", "1987-01-15", "date_reformatted"),
        ("01-01-2020", "2020-01-01", "date_reformatted"),
        ("15-03-2021", "2021-03-15", "date_reformatted"),  # first number above 12 can only be the day
        ("not available", None, "date_unparseable"),
        ("tomorrow", None, "date_unparseable"),
        ("2025-13-01", None, "date_invalid"),
        ("2023-02-30", None, "date_invalid"),
        ("1900-01-01", None, "date_sentinel"),
        ("1800-01-01", None, "date_sentinel"),
        ("2099-01-01", None, "date_sentinel"),
        ("02/30/2020", None, "date_invalid"),
        (None, None, None),
    ],
)
def test_parse_date(raw, expected, rule):
    assert S.parse_date(raw) == (expected, rule)


def test_parse_datetime():
    assert S.parse_datetime("2026-02-22T11:30:00") == ("2026-02-22T11:30:00", None)
    assert S.parse_datetime("2026-02-22 11:30") == ("2026-02-22T11:30:00", "datetime_reformatted")
    assert S.parse_datetime("2099-01-01T00:00:00") == (None, "date_sentinel")
    assert S.parse_datetime("2026-02-22") == ("2026-02-22T00:00:00", "datetime_reformatted")
    assert S.parse_datetime("garbage") == (None, "datetime_unparseable")
    assert S.parse_datetime(None) == (None, None)


def test_parse_time():
    assert S.parse_time("08:30") == ("08:30", None)
    assert S.parse_time("25:99") == (None, "time_invalid")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("(934) 753-7843", "(934) 753-7843"),
        ("2125550199", "(212) 555-0199"),
        ("1-212-555-0199", "(212) 555-0199"),
        ("12345", None),
        ("abc-def-ghij", None),
        ("000-000-0000", None),
        ("John Smith", None),
    ],
)
def test_clean_phone(raw, expected):
    assert S.clean_phone(raw)[0] == expected


def test_clean_email():
    assert S.clean_email("Anthony.Martin@Email.example.com") == (
        "anthony.martin@email.example.com",
        "email_normalised",
    )
    assert S.clean_email("not-an-email")[0] is None
    assert S.clean_email("user@.com")[0] is None


@pytest.mark.parametrize(
    "table, col, raw, expected",
    [
        ("Patients", "gender", "F", "Female"),
        ("Patients", "gender", "Mle", "Male"),
        ("Patients", "gender", "Non-Binary", "Non-Binary"),
        ("Patients", "gender", "robot", None),
        ("Patients", "blood_type", "o+", "O+"),
        ("Patients", "blood_type", "AB", None),
        ("Patients", "marital_status", "married", "Married"),
        ("Patients", "smoking_status", "Smoker", "Current Smoker"),
        ("Patients", "smoking_status", "never assessed", "Never Assessed"),
        ("Patients", "alcohol_consumption", "2 beers/week", "Occasional"),
        ("Patients", "alcohol_consumption", "None", "None"),
        ("Patients", "language_preference", "ENGLISH", "English"),
        ("Patients", "language_preference", "Spanglish", None),
        ("Patients", "ethnicity", "caucasian", "White"),
        ("Patients", "ethnicity", "Human", None),
        ("Patients", "patient_status", "active", "Active"),
        ("Hospitals", "city", "Philly", "Philadelphia"),
        ("Hospitals", "city", "Boston", "Boston"),  # non-strict: unknown values pass through
    ],
)
def test_clean_category(table, col, raw, expected):
    assert S.clean_category(table, col, raw)[0] == expected


@pytest.mark.parametrize(
    "table, col, raw, expected",
    [
        ("Patients", "height_cm", "173", "173"),
        ("Patients", "height_cm", "-10", None),
        ("Patients", "height_cm", "9999", None),
        ("Patients", "height_cm", "tall", None),
        ("Patients", "weight_kg", "650", None),
        ("Patients", "bmi", "150", None),
        ("Doctors", "rating", "10", None),
        ("Doctors", "rating", "4.2", "4.2"),
        ("Doctors", "consultation_fee", "-999", None),
        ("Visits", "oxygen_saturation", "-1", None),
    ],
)
def test_clean_number(table, col, raw, expected):
    assert S.clean_number(table, col, raw)[0] == expected


def test_bmi_from():
    assert S.bmi_from("170", "70") == "24.2"
    assert S.bmi_from("tall", "70") is None
    assert S.bmi_from("0", "70") is None


def test_policy_group_icd():
    assert S.clean_policy("POL-123456")[0] == "POL-123456"
    assert S.clean_policy("POL-ABC")[0] is None
    assert S.clean_group("G1234")[0] is None
    assert S.clean_group("GRP-1234")[0] == "GRP-1234"
    assert S.clean_icd10("E11.9")[0] == "E11.9"
    assert S.clean_icd10("Z23")[0] == "Z23"
    assert S.clean_icd10("INVALID-CODE")[0] is None


def test_null_tokens_respect_column_meaning():
    assert S.is_null_token("N/A") and S.is_null_token("UNKNOWN") and S.is_null_token(" ")
    assert not S.is_null_token("None")  # 'None' is an answer unless the column says otherwise
    assert S.is_null_token("None", none_is_missing=True)


def test_standardise_table_logs_every_change_and_keeps_rows():
    import pandas as pd

    df = pd.DataFrame(
        {
            "patient_id": ["1", "2", "3"],
            "gender": ["F", "Male ", "Mle"],
            "date_of_birth": ["01/15/1987", "2030-01-01", "1990-05-05"],
            "height_cm": ["170", "-10", "180"],
            "weight_kg": ["70", "70", "80"],
            "bmi": [None, "24", "150"],
            "last_name": ["UNKNOWN", "Smith", " Lee "],
            "_row_num": [2, 3, 4],
        }
    ).astype(object)
    log = S.ChangeLog()
    out = S.standardise_table("Patients", df, log)
    assert len(out) == 3
    assert out["gender"].tolist() == ["Female", "Male", "Male"]
    assert out["date_of_birth"].tolist() == ["1987-01-15", None, "1990-05-05"]
    assert out["height_cm"].tolist() == ["170", None, "180"]
    assert out["bmi"].tolist()[0] == "24.2" and out["bmi"].tolist()[1] == "24"
    assert out["last_name"].tolist() == [None, "Smith", "Lee"]
    frame = log.frame()
    assert {"table", "row_num", "column", "old_value", "new_value", "rule"} <= set(frame.columns)
    assert ((frame["column"] == "date_of_birth") & (frame["rule"] == "dob_in_future")).sum() == 1


def test_infer_kinds_and_typing():
    import pandas as pd

    df = pd.DataFrame(
        {
            "hospital_id": ["1", "2"],
            "zip_code": ["02101", "90001"],
            "rating": ["4", "3.5"],
            "emergency_avail": ["True", "False"],
            "established_year": ["1990", None],
            "city": ["A", "B"],
            "_row_num": [2, 3],
        }
    ).astype(object)
    kinds = S.infer_kinds("Hospitals", df)
    assert kinds == {
        "hospital_id": "int",
        "zip_code": "str",
        "rating": "float",
        "emergency_avail": "bool",
        "established_year": "int",
        "city": "str",
    }
    typed = S.to_typed("Hospitals", df)
    assert str(typed["hospital_id"].dtype) == "Int64" and typed["zip_code"].tolist() == ["02101", "90001"]
    assert "_row_num" not in typed.columns


def test_cleaning_summary_empty():
    import pandas as pd

    assert S.cleaning_summary(
        pd.DataFrame(columns=["table", "row_num", "column", "old_value", "new_value", "rule"])
    ).empty
