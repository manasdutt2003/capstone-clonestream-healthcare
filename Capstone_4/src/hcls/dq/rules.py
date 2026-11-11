"""Rule definitions for the data-quality engine (Phase 1, task 1.4).

Two sources of rules:

1. Hand-written rules in ``registry.yaml`` that point at SQL files under ``sql/dq/``.
2. Generated rules (templates below) so that *every* column of *every* table is checked for
   missing values, every foreign key for orphans, and every date / category / numeric column
   for format and range problems.

Every rule, whatever its source, is resolved to the same shape: SQL that returns one row per record with
``yr`` (year for the timeline), ``row_num`` (Excel row), ``failed`` and ``in_scope`` (the denominator).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from hcls import config
from hcls import standardise as S

META_TABLES = {"Referential_Integrity"}

STAKEHOLDER = {
    "Insurance_Claims": "Finance",
    "Billing": "Finance",
    "Patient_Insurance": "Finance",
    "Patients": "PatientCare",
    "Medical_Records": "PatientCare",
    "Prescriptions": "PatientCare",
    "Prescription_Administration": "PatientCare",
    "Admissions": "PatientCare",
    "Patient_Procedures": "PatientCare",
    "Visits": "Compliance",
    "Appointments": "Compliance",
    "Referrals": "Compliance",
    "Hospitals": "Ops",
    "Departments": "Ops",
    "Doctors": "Ops",
    "Hierarchy": "Ops",
    "Nurses": "Ops",
    "Nurse_Assignments": "Ops",
    "Procedure_Codes": "Ops",
}

# Column used for the year timeline of each table.
DATE_COL = {
    "Insurance_Claims": "submitted_date",
    "Visits": "visit_date",
    "Medical_Records": "record_date",
    "Appointments": "appointment_date",
    "Billing": "billing_date",
    "Admissions": "admit_date",
    "Prescriptions": "start_date",
    "Patients": "registration_date",
    "Referrals": "referral_date",
    "Patient_Procedures": "procedure_date",
    "Patient_Insurance": "coverage_start",
    "Nurses": "hire_date",
    "Nurse_Assignments": "shift_date",
    "Prescription_Administration": "administered_datetime",
}

# (child table, child column, parent table, parent column)
FOREIGN_KEYS: list[tuple[str, str, str, str]] = [
    (t, "patient_id", "Patients", "patient_id")
    for t in (
        "Appointments",
        "Visits",
        "Medical_Records",
        "Billing",
        "Prescriptions",
        "Admissions",
        "Insurance_Claims",
        "Patient_Insurance",
        "Referrals",
        "Prescription_Administration",
        "Patient_Procedures",
    )
] + [
    ("Patients", "hospital_id", "Hospitals", "hospital_id"),
    ("Doctors", "hospital_id", "Hospitals", "hospital_id"),
    ("Hierarchy", "hospital_id", "Hospitals", "hospital_id"),
    ("Patients", "primary_care_doctor_id", "Doctors", "doctor_id"),
    ("Appointments", "doctor_id", "Doctors", "doctor_id"),
    ("Medical_Records", "doctor_id", "Doctors", "doctor_id"),
    ("Prescriptions", "doctor_id", "Doctors", "doctor_id"),
    ("Admissions", "attending_doctor_id", "Doctors", "doctor_id"),
    ("Patient_Procedures", "doctor_id", "Doctors", "doctor_id"),
    ("Referrals", "referring_doctor_id", "Doctors", "doctor_id"),
    ("Referrals", "referred_doctor_id", "Doctors", "doctor_id"),
    ("Departments", "head_doctor_id", "Doctors", "doctor_id"),
    ("Departments", "subhead_doctor_id", "Doctors", "doctor_id"),
    ("Doctors", "department_id", "Departments", "department_id"),
    ("Hierarchy", "department_id", "Departments", "department_id"),
    ("Nurse_Assignments", "department_id", "Departments", "department_id"),
    ("Visits", "appointment_id", "Appointments", "appointment_id"),
    ("Medical_Records", "appointment_id", "Appointments", "appointment_id"),
    ("Billing", "appointment_id", "Appointments", "appointment_id"),
    ("Insurance_Claims", "billing_id", "Billing", "billing_id"),
    ("Patient_Insurance", "claim_id", "Insurance_Claims", "claim_id"),
    ("Prescription_Administration", "prescription_id", "Prescriptions", "prescription_id"),
    ("Prescription_Administration", "nurse_id", "Nurses", "nurse_id"),
    ("Nurses", "supervisor_nurse_id", "Nurses", "nurse_id"),
    ("Nurse_Assignments", "nurse_id", "Nurses", "nurse_id"),
    ("Patient_Procedures", "code_id", "Procedure_Codes", "code_id"),
    ("Procedure_Codes", "parent_code_id", "Procedure_Codes", "code_id"),
    ("Patient_Procedures", "admission_id", "Admissions", "admission_id"),
]

# Columns that already have a hand-written completeness rule, so the generic one skips them.
HAND_WRITTEN_NULL_COLS = {
    ("Insurance_Claims", "approved_amount"),
    ("Visits", "appointment_id"),
    ("Medical_Records", "prescribed_meds"),
}
# Columns where an empty value is by design (optional / only exists after an event) -> reported at Low severity.
OPTIONAL_COLS = {
    ("Insurance_Claims", "denial_reason"),
    ("Insurance_Claims", "approved_date"),
    ("Insurance_Claims", "paid_date"),
    ("Billing", "paid_date"),
    ("Appointments", "updated_at"),
    ("Admissions", "discharge_date"),
    ("Admissions", "discharge_time"),
    ("Medical_Records", "follow_up_date"),
    ("Prescriptions", "end_date"),
    ("Referrals", "void_date"),
    ("Medical_Records", "radiology_report"),
    ("Patient_Insurance", "claim_id"),
    ("Patient_Procedures", "admission_id"),
    ("Patient_Procedures", "complications"),
    ("Procedure_Codes", "parent_code_id"),
    ("Nurses", "supervisor_nurse_id"),
}
# Dates that may legitimately be after the as-of date.
FUTURE_OK = {"follow_up_date", "due_date", "coverage_end", "appointment_date", "end_date"}
# Extra range checks that FLAG but never alter data (clinical values and doses could be genuine).
FLAG_BOUNDS: dict[tuple[str, str], tuple[float | None, float | None]] = {
    ("Visits", "systolic_bp"): (60, 250),
    ("Visits", "diastolic_bp"): (30, 150),
    ("Visits", "heart_rate"): (30, 220),
    ("Visits", "temperature_celsius"): (34, 43),
    ("Visits", "respiratory_rate"): (4, 60),
    ("Visits", "pain_level"): (0, 10),
    ("Hospitals", "established_year"): (1850, 2026),
    ("Departments", "established_year"): (1850, 2026),
    ("Prescriptions", "dosage_amount"): (0.001, 5000),
    ("Prescription_Administration", "administered_dosage"): (0.001, 5000),
    ("Hospitals", "total_beds"): (20, None),
    ("Billing", "amount_paid"): (0, None),
}
JSON_COLS = {("Patients", "address"), ("Medical_Records", "radiology_report")}
SPIKE_MIN = 20  # a single date repeated this many times in one column is a default / placeholder


@dataclass
class Rule:
    id: str
    table: str
    column: str | None
    name: str
    check_type: str
    severity: str
    stakeholder: str
    impact: str
    sql: str | None = None
    python_fn: str | None = None
    source: str = "generated"
    extra: dict = field(default_factory=dict)


def _yr(table: str) -> str:
    return f"yr(t.{DATE_COL[table]})" if table in DATE_COL else "CAST(NULL AS VARCHAR)"


def _sql(table: str, fail: str, scope: str = "TRUE", frm: str | None = None) -> str:
    return (
        f"SELECT {_yr(table)} AS yr, t._row_num AS row_num, coalesce({fail}, FALSE) AS failed, "
        f"coalesce({scope}, FALSE) AS in_scope FROM {frm or table + ' AS t'}"
    )


def _q(values: list[str]) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


# ---------------------------------------------------------------- generators


def completeness_rules(columns: dict[str, list[str]]) -> list[Rule]:
    out = []
    for table, cols in columns.items():
        for col in cols:
            if (table, col) in HAND_WRITTEN_NULL_COLS:
                continue
            optional = (table, col) in OPTIONAL_COLS
            sev = (
                "Info"
                if optional
                else ("Medium" if col.endswith("_id") or col in {"first_name", "last_name"} else "Low")
            )
            out.append(
                Rule(
                    f"N-{table}-{col}",
                    table,
                    col,
                    f"{col} is missing",
                    "completeness",
                    sev,
                    STAKEHOLDER[table],
                    "Optional field, empty until the event happens."
                    if optional
                    else f"Missing {col} limits analysis of {table}.",
                    _sql(table, f"missing(t.{col})"),
                )
            )
    return out


def fk_rules() -> list[Rule]:
    out = []
    for child, col, parent, pcol in FOREIGN_KEYS:
        sev = (
            "High"
            if col in {"patient_id", "appointment_id", "billing_id", "claim_id", "prescription_id"}
            else "Medium"
        )
        sql = _sql(
            child,
            f"NOT EXISTS (SELECT 1 FROM {parent} AS p WHERE i(p.{pcol}) = i(t.{col}))",
            f"NOT missing(t.{col})",
        )
        out.append(
            Rule(
                f"R-{child}-{col}",
                child,
                col,
                f"{col} has no matching {parent}.{pcol}",
                "referential",
                sev,
                STAKEHOLDER[child],
                f"Orphan {col}: these {child} rows cannot be joined to {parent}.",
                sql,
            )
        )
    return out


def date_rules() -> list[Rule]:
    out = []
    for table, cols in {**S.DATE_COLS, **S.DATETIME_COLS}.items():
        for col in cols:
            is_ts = col in S.DATETIME_COLS.get(table, [])
            parse = f"ts(t.{col})" if is_ts else f"d(t.{col})"
            out.append(
                Rule(
                    f"F-{table}-{col}",
                    table,
                    col,
                    f"{col} is not a valid ISO date",
                    "validity",
                    "Medium",
                    STAKEHOLDER[table],
                    "Text dates (dd-mm-yyyy, mm/dd/yyyy, words) or impossible dates break sorting and ageing.",
                    _sql(table, f"{parse} IS NULL", f"NOT missing(t.{col})"),
                )
            )
            sentinel = "'" + "', '".join(sorted(S.SENTINEL_DATES)) + "'"
            out.append(
                Rule(
                    f"S-{table}-{col}",
                    table,
                    col,
                    f"{col} holds a placeholder date",
                    "validity",
                    "Medium",
                    STAKEHOLDER[table],
                    "Placeholder dates such as 1900-01-01 or 2099-01-01 stand in for 'no date' and corrupt date maths.",
                    _sql(table, f"substr(t.{col}, 1, 10) IN ({sentinel})", f"NOT missing(t.{col})"),
                )
            )
            out.append(
                Rule(
                    f"P-{table}-{col}",
                    table,
                    col,
                    f"{col}: one date repeated {SPIKE_MIN}+ times",
                    "validity",
                    "Low",
                    STAKEHOLDER[table],
                    "A single date appearing this often is a default value, not a real event.",
                    _sql(
                        table,
                        f"count(*) OVER (PARTITION BY substr(t.{col}, 1, 10)) >= {SPIKE_MIN}",
                        f"NOT missing(t.{col})",
                    ),
                )
            )
            if col not in FUTURE_OK:
                out.append(
                    Rule(
                        f"T-{table}-{col}",
                        table,
                        col,
                        f"{col} is after the as-of date",
                        "timeliness",
                        "Low",
                        STAKEHOLDER[table],
                        "Dated in the future relative to the as-of date; an event cannot already be recorded.",
                        _sql(
                            table,
                            f"{parse} > CAST(as_of() AS TIMESTAMP)" if is_ts else f"{parse} > as_of()",
                            f"{parse} IS NOT NULL",
                        ),
                    )
                )
    for table, cols in S.TIME_COLS.items():
        for col in cols:
            out.append(
                Rule(
                    f"F-{table}-{col}",
                    table,
                    col,
                    f"{col} is not HH:MM",
                    "validity",
                    "Low",
                    STAKEHOLDER[table],
                    "Invalid time of day.",
                    _sql(
                        table,
                        f"NOT regexp_matches(t.{col}, '^([01][0-9]|2[0-3]):[0-5][0-9]$')",
                        f"NOT missing(t.{col})",
                    ),
                )
            )
    return out


def format_rules() -> list[Rule]:
    out = []
    for table, cols in S.PHONE_COLS.items():
        for col in cols:
            out.append(
                Rule(
                    f"F-{table}-{col}",
                    table,
                    col,
                    f"{col} is not '(ddd) ddd-dddd'",
                    "validity",
                    "Medium",
                    STAKEHOLDER[table],
                    "Patients and next of kin cannot be contacted; mixed formats break de-duplication.",
                    _sql(
                        table,
                        f"NOT regexp_matches(t.{col}, '^[(][0-9]{{3}}[)] [0-9]{{3}}-[0-9]{{4}}$')",
                        f"NOT missing(t.{col})",
                    ),
                )
            )
    for table, cols in S.EMAIL_COLS.items():
        for col in cols:
            out.append(
                Rule(
                    f"F-{table}-{col}",
                    table,
                    col,
                    f"{col} is not a valid e-mail",
                    "validity",
                    "Medium",
                    STAKEHOLDER[table],
                    "Invalid addresses cannot receive statements or reminders.",
                    _sql(
                        table,
                        f"NOT regexp_matches(t.{col}, '^[^@ ]+@[^@ .][^@ ]*[.][A-Za-z]{{2,}}$')",
                        f"NOT missing(t.{col})",
                    ),
                )
            )
    for table, col, pat, nice in (
        ("Patients", "insurance_policy_number", "^POL-[0-9]{6}$", "POL-dddddd"),
        ("Patients", "insurance_group_number", "^GRP-[0-9]{4}$", "GRP-dddd"),
        ("Patient_Insurance", "policy_number", "^POL-[0-9]{6}$", "POL-dddddd"),
        ("Patient_Insurance", "group_number", "^GRP-[0-9]{4}$", "GRP-dddd"),
        ("Medical_Records", "diagnosis_code", r"^[A-Z][0-9]{2}([.][0-9]{1,4})?$", "an ICD-10 code"),
    ):
        out.append(
            Rule(
                f"F-{table}-{col}",
                table,
                col,
                f"{col} is not {nice}",
                "validity",
                "Medium",
                STAKEHOLDER[table],
                "Malformed identifier; insurer or coding look-ups will fail.",
                _sql(table, f"NOT regexp_matches(t.{col}, '{pat}')", f"NOT missing(t.{col})"),
            )
        )
    for table, col in sorted(JSON_COLS):
        out.append(
            Rule(
                f"J-{table}-{col}",
                table,
                col,
                f"{col} is not valid JSON",
                "validity",
                "Low",
                STAKEHOLDER[table],
                "Structured field cannot be parsed.",
                _sql(table, f"NOT json_valid(t.{col})", f"NOT missing(t.{col})"),
            )
        )
    return out


def domain_rules() -> list[Rule]:
    out = []
    for (table, col), (canonical, aliases, strict) in S.CATEGORIES.items():
        if strict:
            fail = f"t.{col} NOT IN ({_q(canonical)})"
            nice = "outside the allowed list (spelling / case / abbreviation variants)"
        else:
            fail = f"lower(t.{col}) IN ({_q(sorted(aliases))})"
            nice = "uses an abbreviation instead of the full name"
        out.append(
            Rule(
                f"V-{table}-{col}",
                table,
                col,
                f"{col} {nice}",
                "validity",
                "Medium",
                STAKEHOLDER[table],
                "Variant spellings split one category into several and understate every group count.",
                _sql(table, fail, f"NOT missing(t.{col})"),
            )
        )
    return out


def bounds_rules() -> list[Rule]:
    out = []
    for (table, col), (lo, hi) in S.NUMERIC_BOUNDS.items():
        out.append(_bound_rule(table, col, lo, hi, "B", "Medium", "Impossible value (cleaned to NULL)."))
    for (table, col), (lo, hi) in FLAG_BOUNDS.items():
        out.append(
            _bound_rule(table, col, lo, hi, "X", "Medium", "Out-of-range value (flagged, not changed).")
        )
    return out


def _bound_rule(table, col, lo, hi, prefix, sev, impact) -> Rule:
    conds = [f"n(t.{col}) IS NULL"]
    if lo is not None:
        conds.append(f"n(t.{col}) < {lo}")
    if hi is not None:
        conds.append(f"n(t.{col}) > {hi}")
    rng = f"{lo if lo is not None else '-inf'} to {hi if hi is not None else '+inf'}"
    return Rule(
        f"{prefix}-{table}-{col}",
        table,
        col,
        f"{col} is non-numeric or outside {rng}",
        "validity",
        sev,
        STAKEHOLDER[table],
        impact,
        _sql(table, " OR ".join(conds), f"NOT missing(t.{col})"),
    )


def generated_rules(columns: dict[str, list[str]]) -> list[Rule]:
    return (
        completeness_rules(columns)
        + fk_rules()
        + date_rules()
        + format_rules()
        + domain_rules()
        + bounds_rules()
    )


# ---------------------------------------------------------------- registry + python rules


def a33_procedure_code_cycles(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Flag procedure codes that sit on, or lead into, a parent cycle."""
    df = frames["Procedure_Codes"]
    parent = {}
    for cid, pid in zip(df["code_id"], df["parent_code_id"], strict=True):
        try:
            parent[int(cid)] = int(float(pid)) if pid is not None else None
        except ValueError:
            parent[int(cid)] = None
    bad = set()
    for start in parent:
        seen, cur = [], start
        while cur is not None and cur in parent:
            if cur in seen:
                bad.update(seen)
                break
            seen.append(cur)
            cur = parent[cur]
    return pd.DataFrame(
        {
            "yr": [None] * len(df),
            "row_num": df["_row_num"].tolist(),
            "failed": [int(c) in bad for c in df["code_id"]],
            "in_scope": [True] * len(df),
        }
    )


PYTHON_RULES: dict[str, Callable[[dict[str, pd.DataFrame]], pd.DataFrame]] = {
    "a33_procedure_code_cycles": a33_procedure_code_cycles,
}


def load_registry(sql_dir: Path | None = None, registry: Path | None = None) -> list[Rule]:
    sql_dir = sql_dir or (config.project_root() / config.load_config()["paths"]["sql_dir"] / "dq")
    registry = registry or config.path("dq_registry")
    spec = yaml.safe_load(registry.read_text(encoding="utf-8"))["rules"]
    rules = []
    for r in spec:
        sql = (sql_dir / r["sql_file"]).read_text(encoding="utf-8") if r.get("sql_file") else None
        rules.append(
            Rule(
                r["id"],
                r["table"],
                r.get("column"),
                r["name"],
                r["check_type"],
                r["severity"],
                r["stakeholder"],
                r["impact"],
                sql=sql,
                python_fn=r.get("python_fn"),
                source="registry",
            )
        )
    return rules


def build_rules(columns: dict[str, list[str]]) -> list[Rule]:
    rules = load_registry() + generated_rules(columns)
    ids = [r.id for r in rules]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate rule ids: {sorted(dupes)}")
    return rules
