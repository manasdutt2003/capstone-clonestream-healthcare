"""Phase 1 / task 1.3 - bronze -> silver standardisation ("the cleaning step").

Principles (SPEC section 6a, DECISIONS D-005 / D-009):

* Rows are NEVER dropped. Every change is written to a change log (table, row, column, old, new, rule).
* We fix FORMAT problems (dates, phones, casing, spelling variants, placeholder text).
* We null values that are IMPOSSIBLE by definition (height of -10 cm, a birth date in the future,
  an e-mail of "not-an-email"). We never invent a value, except BMI, which is a pure formula of
  height and weight.
* We do NOT touch money fields, doses or foreign keys. Those are flagged by the DQ engine, because
  "fixing" them would hide exactly the evidence the auditors need.
* Silver is kept as canonical TEXT so the same SQL rules can be re-run on raw and clean data to
  prove what the cleaning fixed (and what it deliberately left alone).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable

import pandas as pd

from hcls import config
from hcls.ingest import data_columns

# --------------------------------------------------------------------------------------
# Configuration tables
# --------------------------------------------------------------------------------------

# Text that means "we do not know" in any column. (Whether the literal 'None' is missing depends on the column.)
NULL_TOKENS = {"", "n/a", "na", "#n/a", "null", "unknown", "nan"}
# Columns where the literal text 'None' is a MISSING value rather than the answer "none".
# Medical_Records.prescribed_meds follows the brief, which counts these 40 rows as the missing-medication defect.
NONE_IS_MISSING = {("Medical_Records", "prescribed_meds")}

DATE_COLS: dict[str, list[str]] = {
    "Patients": ["date_of_birth", "registration_date", "last_visit_date"],
    "Medical_Records": ["record_date", "follow_up_date"],
    "Billing": ["billing_date", "due_date", "paid_date"],
    "Visits": ["visit_date"],
    "Prescriptions": ["start_date", "end_date"],
    "Insurance_Claims": ["submitted_date", "approved_date", "paid_date"],
    "Admissions": ["admit_date", "discharge_date"],
    "Nurses": ["hire_date"],
    "Nurse_Assignments": ["shift_date"],
    "Referrals": ["referral_date", "void_date"],
    "Patient_Insurance": ["coverage_start", "coverage_end"],
    "Prescription_Administration": ["administered_datetime"],
    "Patient_Procedures": ["procedure_date"],
}
DATETIME_COLS: dict[str, list[str]] = {"Appointments": ["appointment_date", "created_at", "updated_at"]}
TIME_COLS: dict[str, list[str]] = {"Admissions": ["admit_time", "discharge_time"]}

PHONE_COLS: dict[str, list[str]] = {
    "Patients": ["phone_number", "emergency_contact_phone"],
    "Hospitals": ["phone_number"],
    "Doctors": ["phone_number"],
}
EMAIL_COLS: dict[str, list[str]] = {"Patients": ["email"], "Doctors": ["email"]}

# (table, column) -> (canonical values, {lower-case alias: canonical}, strict)
# strict=True  : anything that is not canonical or a known alias becomes NULL
# strict=False : only the known aliases are rewritten, everything else passes through
CATEGORIES: dict[tuple[str, str], tuple[list[str], dict[str, str], bool]] = {
    ("Patients", "gender"): (
        ["Male", "Female", "Non-Binary"],
        {"f": "Female", "m": "Male", "mle": "Male", "fem": "Female", "nonbinary": "Non-Binary"},
        True,
    ),
    ("Patients", "blood_type"): (["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"], {}, True),
    ("Patients", "marital_status"): (["Married", "Single", "Divorced", "Separated", "Widowed"], {}, True),
    ("Patients", "smoking_status"): (
        ["Non-Smoker", "Former Smoker", "Current Smoker", "Never Assessed"],
        {"smoker": "Current Smoker"},
        True,
    ),
    ("Patients", "alcohol_consumption"): (
        ["None", "Occasional", "Moderate", "Heavy", "Former"],
        {"sometimes": "Occasional", "2 beers/week": "Occasional"},
        True,
    ),
    ("Patients", "language_preference"): (
        [
            "English",
            "Spanish",
            "Mandarin",
            "Tagalog",
            "Cantonese",
            "Korean",
            "Vietnamese",
            "French",
            "Arabic",
            "Russian",
        ],
        {},
        True,
    ),
    ("Patients", "ethnicity"): (
        ["White", "Hispanic or Latino", "Black or African American", "Asian", "Two or More Races", "Other"],
        {"caucasian": "White"},
        True,
    ),
    ("Patients", "patient_status"): (["Active", "Inactive", "Deceased"], {}, True),
    ("Hospitals", "city"): (
        [],
        {
            "philly": "Philadelphia",
            "jax": "Jacksonville",
            "indy": "Indianapolis",
            "sf": "San Francisco",
            "okc": "Oklahoma City",
            "dc": "Washington",
            "vegas": "Las Vegas",
        },
        False,
    ),
}

# Impossible-by-definition numeric ranges. Outside the range -> NULL (and logged).
NUMERIC_BOUNDS: dict[tuple[str, str], tuple[float | None, float | None]] = {
    ("Patients", "height_cm"): (50, 250),
    ("Patients", "weight_kg"): (2, 300),
    ("Patients", "bmi"): (10, 80),
    ("Doctors", "years_exp"): (0, 60),
    ("Doctors", "rating"): (0, 5),
    ("Doctors", "consultation_fee"): (0.01, None),
    ("Visits", "oxygen_saturation"): (50, 100),
}

# Placeholder dates that databases use for "no date". They are not real events, so they become NULL.
SENTINEL_DATES = {"1800-01-01", "1900-01-01", "2099-01-01", "9999-12-31", "0001-01-01"}

ICD10_RE = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.][^@\s]*\.[A-Za-z]{2,}$")
POLICY_RE = re.compile(r"^POL-\d{6}$")
GROUP_RE = re.compile(r"^GRP-\d{4}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$")
US_DATE_RE = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

Result = tuple[str | None, str | None]  # (new value, rule label if changed)


# --------------------------------------------------------------------------------------
# Atomic value cleaners (pure functions, unit tested)
# --------------------------------------------------------------------------------------


def is_null_token(value: str | None, none_is_missing: bool = False) -> bool:
    if value is None:
        return True
    v = value.strip().lower()
    return v in NULL_TOKENS or (none_is_missing and v == "none")


def parse_date(value: str | None) -> Result:
    """Return an ISO yyyy-mm-dd string. Day/month order for dashed or slashed dates is US (mm-dd-yyyy)
    unless the first number is above 12 (then it must be the day). See DECISIONS D-007."""
    if value is None:
        return None, None
    v = value.strip()
    if ISO_DATE_RE.match(v):
        try:
            dt.date.fromisoformat(v)
        except ValueError:
            return None, "date_invalid"
        return (None, "date_sentinel") if v in SENTINEL_DATES else (v, None)
    if ISO_TS_RE.match(v):
        return (None, "date_sentinel") if v[:10] in SENTINEL_DATES else (v[:10], "date_trimmed_time")
    m = US_DATE_RE.match(v)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        month, day = (a, b) if a <= 12 else (b, a)
        try:
            out = dt.date(y, month, day).isoformat()
        except ValueError:
            return None, "date_invalid"
        return (None, "date_sentinel") if out in SENTINEL_DATES else (out, "date_reformatted")
    return None, "date_unparseable"


def parse_datetime(value: str | None) -> Result:
    if value is None:
        return None, None
    v = value.strip()
    if ISO_TS_RE.match(v):
        norm = v.replace(" ", "T")
        if norm[:10] in SENTINEL_DATES:
            return None, "date_sentinel"
        if len(norm) == 16:
            norm += ":00"
        try:
            dt.datetime.fromisoformat(norm)
        except ValueError:
            return None, "datetime_invalid"
        return norm, (None if norm == v else "datetime_reformatted")
    d, rule = parse_date(v)
    if d:
        return d + "T00:00:00", "datetime_reformatted"
    return None, "datetime_unparseable"


def parse_time(value: str | None) -> Result:
    if value is None:
        return None, None
    v = value.strip()
    return (v, None) if TIME_RE.match(v) else (None, "time_invalid")


def clean_phone(value: str | None) -> Result:
    """Standard US form '(ddd) ddd-dddd'. Anything that is not 10 digits (or 11 starting with 1) is NULL."""
    if value is None:
        return None, None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10 and len(set(digits)) > 1:
        out = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        return out, (None if out == value else "phone_reformatted")
    return None, "phone_invalid"


def clean_email(value: str | None) -> Result:
    if value is None:
        return None, None
    v = value.strip().lower()
    if EMAIL_RE.match(v):
        return v, (None if v == value else "email_normalised")
    return None, "email_invalid"


def clean_policy(value: str | None) -> Result:
    if value is None:
        return None, None
    return (value, None) if POLICY_RE.match(value) else (None, "policy_placeholder")


def clean_group(value: str | None) -> Result:
    if value is None:
        return None, None
    return (value, None) if GROUP_RE.match(value) else (None, "group_placeholder")


def clean_category(table: str, col: str, value: str | None) -> Result:
    if value is None:
        return None, None
    canonical, aliases, strict = CATEGORIES[(table, col)]
    lookup = {c.lower(): c for c in canonical} | aliases
    key = value.strip().lower()
    if key in lookup:
        new = lookup[key]
        return new, (None if new == value else "category_standardised")
    if strict:
        return None, "category_unmapped"
    return value, None


def clean_number(table: str, col: str, value: str | None) -> Result:
    if value is None:
        return None, None
    lo, hi = NUMERIC_BOUNDS[(table, col)]
    try:
        x = float(value)
    except ValueError:
        return None, "number_non_numeric"
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        return None, "number_out_of_range"
    return value, None


def clean_icd10(value: str | None) -> Result:
    if value is None:
        return None, None
    return (value, None) if ICD10_RE.match(value) else (None, "icd10_invalid")


def bmi_from(height_cm: str | None, weight_kg: str | None) -> str | None:
    try:
        h, w = float(height_cm), float(weight_kg)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if h <= 0:
        return None
    return f"{w / (h / 100) ** 2:.1f}"


# --------------------------------------------------------------------------------------
# Table-level driver
# --------------------------------------------------------------------------------------


class ChangeLog:
    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def record(self, table: str, row_num: int, col: str, old, new, rule: str) -> None:
        self.rows.append((table, row_num, col, old, new, rule))

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            self.rows, columns=["table", "row_num", "column", "old_value", "new_value", "rule"]
        )


def _apply(
    df: pd.DataFrame, table: str, col: str, fn: Callable[[str | None], Result], log: ChangeLog
) -> None:
    if col not in df.columns:
        return
    old_vals = df[col].tolist()
    rows = df["_row_num"].tolist()
    new_vals: list[str | None] = []
    for row, old in zip(rows, old_vals, strict=True):
        new, rule = fn(old)
        new_vals.append(new)
        if rule and new != old:
            log.record(table, row, col, old, new, rule)
    df[col] = pd.Series(new_vals, index=df.index, dtype=object)


def standardise_table(table: str, bronze: pd.DataFrame, log: ChangeLog) -> pd.DataFrame:
    df = bronze.astype(object).where(bronze.notna(), None)
    cols = data_columns(df)

    # 1. trim whitespace everywhere; map placeholder text to NULL
    for col in cols:
        none_missing = (table, col) in NONE_IS_MISSING

        def _trim(v, none_missing=none_missing):
            if v is None:
                return None, None
            s = v.strip()
            if is_null_token(s, none_missing):
                return None, "placeholder_to_null"
            if s != v:
                return s, "whitespace_trimmed"
            return v, None

        _apply(df, table, col, _trim, log)

    # 2. dates / timestamps / times
    for col in DATE_COLS.get(table, []):
        _apply(df, table, col, parse_date, log)
    for col in DATETIME_COLS.get(table, []):
        _apply(df, table, col, parse_datetime, log)
    for col in TIME_COLS.get(table, []):
        _apply(df, table, col, parse_time, log)

    # 3. contact details
    for col in PHONE_COLS.get(table, []):
        _apply(df, table, col, clean_phone, log)
    for col in EMAIL_COLS.get(table, []):
        _apply(df, table, col, clean_email, log)

    # 4. categories
    for (t, col), _ in CATEGORIES.items():
        if t == table:
            _apply(df, table, col, lambda v, t=t, col=col: clean_category(t, col, v), log)

    # 5. numeric bounds
    for (t, col), _ in NUMERIC_BOUNDS.items():
        if t == table:
            _apply(df, table, col, lambda v, t=t, col=col: clean_number(t, col, v), log)

    # 6. table specific rules
    if table == "Patients":
        _apply(df, table, "insurance_policy_number", clean_policy, log)
        _apply(df, table, "insurance_group_number", clean_group, log)
        asof = config.as_of_date().isoformat()
        _apply(
            df,
            table,
            "date_of_birth",
            lambda v: (None, "dob_in_future") if v and v > asof else (v, None),
            log,
        )
        _fix_bmi(df, log)
    elif table == "Patient_Insurance":
        _apply(df, table, "policy_number", clean_policy, log)
        _apply(df, table, "group_number", clean_group, log)
    elif table == "Medical_Records":
        _apply(df, table, "diagnosis_code", clean_icd10, log)
    elif table == "Referrals":
        # 2 rows hold a date where a patient id belongs (column shift). The id cannot be recovered.
        _apply(
            df,
            table,
            "patient_id",
            lambda v: (None, "id_holds_date") if v and ISO_DATE_RE.match(v) else (v, None),
            log,
        )
    return df


def _fix_bmi(df: pd.DataFrame, log: ChangeLog) -> None:
    """BMI is a formula of height and weight, so it is the one value we may (re)compute."""
    new_vals, rows = [], df["_row_num"].tolist()
    for row, h, w, b in zip(rows, df["height_cm"], df["weight_kg"], df["bmi"], strict=True):
        calc = bmi_from(h, w)
        if calc is not None and b is None:
            new_vals.append(calc)
            log.record("Patients", row, "bmi", b, calc, "bmi_recomputed")
        else:
            new_vals.append(b)
    df["bmi"] = pd.Series(new_vals, index=df.index, dtype=object)


def standardise(bronze: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    log = ChangeLog()
    silver = {name: standardise_table(name, df, log) for name, df in bronze.items()}
    return silver, log.frame()


def cleaning_summary(changes: pd.DataFrame) -> pd.DataFrame:
    if changes.empty:
        return pd.DataFrame(columns=["table", "column", "rule", "cells_changed"])
    return (
        changes.groupby(["table", "column", "rule"], as_index=False)
        .size()
        .rename(columns={"size": "cells_changed"})
        .sort_values(["table", "column", "rule"])
        .reset_index(drop=True)
    )


# --------------------------------------------------------------------------------------
# Typed export (clean workbook)
# --------------------------------------------------------------------------------------

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


def infer_kinds(table: str, df: pd.DataFrame) -> dict[str, str]:
    """Return {column: kind} where kind is int|float|bool|date|datetime|str."""
    kinds: dict[str, str] = {}
    for col in data_columns(df):
        if col in DATE_COLS.get(table, []):
            kinds[col] = "date"
            continue
        if col in DATETIME_COLS.get(table, []):
            kinds[col] = "datetime"
            continue
        vals = [v for v in df[col].tolist() if isinstance(v, str)]
        if not vals:
            kinds[col] = "str"
        elif all(v in ("True", "False") for v in vals):
            kinds[col] = "bool"
        elif any(len(v) > 1 and v.lstrip("-").startswith("0") and v.isdigit() for v in vals):
            kinds[col] = "str"  # leading zeros (zip codes) must survive
        elif all(_INT_RE.match(v) for v in vals):
            kinds[col] = "int"
        elif all(_INT_RE.match(v) or _FLOAT_RE.match(v) for v in vals):
            kinds[col] = "float"
        else:
            kinds[col] = "str"
    return kinds


def to_typed(table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Typed copy for Excel/Power BI. Lineage columns are dropped."""
    kinds = infer_kinds(table, df)
    out = pd.DataFrame(index=df.index)
    for col, kind in kinds.items():
        s = df[col]
        if kind == "int":
            out[col] = pd.to_numeric(s, errors="coerce").astype("Int64")
        elif kind == "float":
            out[col] = pd.to_numeric(s, errors="coerce").astype("Float64")
        elif kind == "bool":
            out[col] = s.map({"True": True, "False": False}).astype("boolean")
        elif kind == "date":
            out[col] = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
        elif kind == "datetime":
            out[col] = pd.to_datetime(s, format="%Y-%m-%dT%H:%M:%S", errors="coerce")
        else:
            out[col] = s
    return out
