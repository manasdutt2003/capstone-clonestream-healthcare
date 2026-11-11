"""Ingest-time validators (Phase 4, task 4.3): the checks that would have stopped each issue at the door.

Each check returns the rows it would REJECT. Every check names the issue it prevents, so the remediation plan can say
"this validator stops C02". `validate(frames)` runs them all; run on the existing data it also shows how many bad rows
each one would have blocked.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from hcls import config
from hcls.dq.rules import FOREIGN_KEYS
from hcls.remediation.common import blank, date, num

PLACEHOLDER_IDS = {88888}
DECIDED = ("Approved", "Denied", "Appealed")
CLAIM_STATUSES = ("Approved", "Denied", "Appealed", "Submitted", "Pending", "In Review")
APPOINTMENT_STATUSES = ("Cancelled", "Completed", "No-Show", "Pending")
PAYMENT_LINKS = [  # child table, child key, parent table, parent key (checked for the SAME patient)
    ("Insurance_Claims", "billing_id", "Billing", "billing_id"),
    ("Patient_Insurance", "claim_id", "Insurance_Claims", "claim_id"),
    ("Prescription_Administration", "prescription_id", "Prescriptions", "prescription_id"),
    ("Visits", "appointment_id", "Appointments", "appointment_id"),
    ("Medical_Records", "appointment_id", "Appointments", "appointment_id"),
    ("Billing", "appointment_id", "Appointments", "appointment_id"),
]
PATIENT_LINK_ISSUE = {
    "Insurance_Claims": "A02",
    "Patient_Insurance": "A38",
    "Prescription_Administration": "A30",
    "Visits": "A02-class link",
    "Medical_Records": "A02-class link",
    "Billing": "A02-class link",
}


@dataclass(frozen=True)
class Check:
    id: str
    table: str
    kind: str  # not_null | foreign_key | same_patient | sentinel | range | date_order | enum | unique | business
    column: str
    issue: str  # the finding it prevents
    description: str
    mask: Callable[[pd.DataFrame, dict[str, pd.DataFrame]], pd.Series]  # True = reject


def _mask_not_null(col: str, only_when: Callable[[pd.DataFrame], pd.Series] | None = None):
    def f(df, _):
        m = blank(df[col])
        return m & only_when(df) if only_when else m

    return f


def _mask_fk(col: str, parent: str, pcol: str):
    def f(df, ctx):
        if parent not in ctx:
            return pd.Series(False, index=df.index)
        ids = set(num(ctx[parent][pcol]).dropna())
        v = num(df[col])
        return v.notna() & ~v.isin(ids)

    return f


def _mask_same_patient(col: str, parent: str, pcol: str):
    def f(df, ctx):
        if parent not in ctx:
            return pd.Series(False, index=df.index)
        p = ctx[parent]
        owner = dict(zip(num(p[pcol]), num(p["patient_id"]), strict=True))
        mapped = num(df[col]).map(owner)
        return mapped.notna() & (mapped != num(df["patient_id"]))

    return f


def _mask_sentinel(df, _):
    v = num(df["patient_id"])
    return v.notna() & ((v <= 0) | v.isin(PLACEHOLDER_IDS) | v.between(99990, 99999))


def _mask_unique(col: str):
    return lambda df, _: (
        ~blank(df[col]) & df[col].duplicated(keep="first")
    )  # the second and later rows are rejected


def _mask_date_order(first: str, second: str):
    return lambda df, _: (
        date(df[first]).notna() & date(df[second]).notna() & (date(df[second]) < date(df[first]))
    )


def _mask_future(col: str):
    asof = pd.Timestamp(config.as_of_date())
    return lambda df, _: date(df[col]) > asof


def _mask_enum(col: str, allowed: tuple[str, ...]):
    return lambda df, _: ~blank(df[col]) & ~df[col].isin(allowed)


def _build() -> list[Check]:
    out: list[Check] = []
    out += [
        Check(
            "V-C01",
            "Insurance_Claims",
            "not_null",
            "approved_amount",
            "C01",
            "approved_amount required once the claim is Approved, Denied or Appealed",
            _mask_not_null("approved_amount", lambda d: d["claim_status"].isin(DECIDED)),
        ),
        Check(
            "V-C02",
            "Visits",
            "not_null",
            "appointment_id",
            "C02",
            "every visit must reference an appointment (or be flagged as a walk-in)",
            _mask_not_null("appointment_id"),
        ),
        Check(
            "V-C03",
            "Medical_Records",
            "not_null",
            "prescribed_meds",
            "C03",
            "prescribed_meds required; 'no medication' must be an explicit code, not text 'None'",
            _mask_not_null("prescribed_meds"),
        ),
    ]
    for child, col, parent, pcol in FOREIGN_KEYS:
        if col == "patient_id":
            out.append(
                Check(
                    f"V-FK-{child}-{col}",
                    child,
                    "foreign_key",
                    col,
                    f"R-{child}-{col}",
                    f"{col} must exist in {parent}",
                    _mask_fk(col, parent, pcol),
                )
            )
            out.append(
                Check(
                    f"V-SENT-{child}",
                    child,
                    "sentinel",
                    col,
                    f"R-{child}-{col}",
                    "patient_id must not be a placeholder (0, negative, 88888, 9999x)",
                    _mask_sentinel,
                )
            )
    out += [
        Check(
            "V-FK-Billing-appointment_id",
            "Billing",
            "foreign_key",
            "appointment_id",
            "R-Billing-appointment_id",
            "appointment_id must exist in Appointments",
            _mask_fk("appointment_id", "Appointments", "appointment_id"),
        ),
        Check(
            "V-FK-Medical_Records-appointment_id",
            "Medical_Records",
            "foreign_key",
            "appointment_id",
            "R-Medical_Records-appointment_id",
            "appointment_id must exist in Appointments",
            _mask_fk("appointment_id", "Appointments", "appointment_id"),
        ),
    ]
    for child, col, parent, pcol in PAYMENT_LINKS:
        out.append(
            Check(
                f"V-LINK-{child}-{col}",
                child,
                "same_patient",
                col,
                PATIENT_LINK_ISSUE[child],
                f"the {parent} row named by {col} must belong to the same patient",
                _mask_same_patient(col, parent, pcol),
            )
        )
    out += [
        Check(
            "V-A01",
            "Insurance_Claims",
            "unique",
            "billing_id",
            "A01",
            "a bill may be linked to at most one claim",
            _mask_unique("billing_id"),
        ),
        Check(
            "V-A16",
            "Patients",
            "unique",
            "patient_id",
            "A16",
            "patient_id must be unique",
            _mask_unique("patient_id"),
        ),
        Check(
            "V-A07",
            "Insurance_Claims",
            "range",
            "submitted_amount",
            "A07",
            "submitted_amount must not be negative",
            lambda d, _: num(d["submitted_amount"]) < 0,
        ),
        Check(
            "V-A44",
            "Insurance_Claims",
            "range",
            "approved_amount",
            "A44",
            "approved_amount must not exceed submitted_amount",
            lambda d, _: num(d["approved_amount"]) > num(d["submitted_amount"]),
        ),
        Check(
            "V-A11",
            "Billing",
            "range",
            "total_amount",
            "A11",
            "total_amount must not be negative",
            lambda d, _: num(d["total_amount"]) < 0,
        ),
        Check(
            "V-A09",
            "Billing",
            "range",
            "total_amount",
            "A09",
            "insurance_covered + patient_responsibility must equal total_amount",
            lambda d, _: (
                (
                    num(d["insurance_covered"]) + num(d["patient_responsibility"]) - num(d["total_amount"])
                ).abs()
                > 0.01
            ),
        ),
        Check(
            "V-A10",
            "Billing",
            "range",
            "amount_paid",
            "A10",
            "amount_paid must not exceed patient_responsibility",
            lambda d, _: num(d["amount_paid"]) > num(d["patient_responsibility"]),
        ),
        Check(
            "V-A24",
            "Admissions",
            "date_order",
            "discharge_date",
            "A24",
            "discharge_date must not be before admit_date",
            _mask_date_order("admit_date", "discharge_date"),
        ),
        Check(
            "V-A28",
            "Prescriptions",
            "date_order",
            "end_date",
            "A28",
            "end_date must not be before start_date",
            _mask_date_order("start_date", "end_date"),
        ),
        Check(
            "V-DO-claims-approved",
            "Insurance_Claims",
            "date_order",
            "approved_date",
            "date order",
            "approved_date must not be before submitted_date",
            _mask_date_order("submitted_date", "approved_date"),
        ),
        Check(
            "V-DO-claims-paid",
            "Insurance_Claims",
            "date_order",
            "paid_date",
            "date order",
            "paid_date must not be before approved_date",
            _mask_date_order("approved_date", "paid_date"),
        ),
        Check(
            "V-FUT-claims-submitted",
            "Insurance_Claims",
            "date_order",
            "submitted_date",
            "T-*",
            "submitted_date must not be after the as-of date",
            _mask_future("submitted_date"),
        ),
        Check(
            "V-FUT-claims-paid",
            "Insurance_Claims",
            "date_order",
            "paid_date",
            "T-*",
            "paid_date must not be after the as-of date",
            _mask_future("paid_date"),
        ),
        Check(
            "V-ENUM-claim_status",
            "Insurance_Claims",
            "enum",
            "claim_status",
            "domain",
            "claim_status must be one of the six known statuses",
            _mask_enum("claim_status", CLAIM_STATUSES),
        ),
        Check(
            "V-ENUM-appointment_status",
            "Appointments",
            "enum",
            "status",
            "domain",
            "appointment status must be a known value",
            _mask_enum("status", APPOINTMENT_STATUSES),
        ),
        Check(
            "V-A12",
            "Billing",
            "business",
            "appointment_id",
            "A12",
            "no bill for a Cancelled or No-Show appointment",
            _mask_cancelled_bill,
        ),
    ]
    return out


def _mask_cancelled_bill(df, ctx):
    if "Appointments" not in ctx:
        return pd.Series(False, index=df.index)
    a = ctx["Appointments"]
    bad = set(num(a.loc[a["status"].isin(["Cancelled", "No-Show"]), "appointment_id"]).dropna())
    return num(df["appointment_id"]).isin(bad)


CHECKS: list[Check] = _build()


def validate_table(
    name: str, df: pd.DataFrame, context: dict[str, pd.DataFrame] | None = None, strict: bool = False
) -> pd.DataFrame:
    """Rows of `df` that any check for `name` would reject.

    A check whose columns are missing from `df` is skipped, unless `strict` (then the missing column is an error).
    """
    context = context or {}
    rows = []
    for c in (c for c in CHECKS if c.table == name):
        if c.column not in df.columns:
            continue
        try:
            bad = c.mask(df, context).fillna(False)
        except KeyError:
            if strict:
                raise
            continue
        for idx in df.index[bad.to_numpy()]:
            rows.append(
                {
                    "check_id": c.id,
                    "table": name,
                    "column": c.column,
                    "kind": c.kind,
                    "issue_prevented": c.issue,
                    "row_num": df.at[idx, "_row_num"] if "_row_num" in df.columns else idx,
                    "rule": c.description,
                }
            )
    return pd.DataFrame(
        rows, columns=["check_id", "table", "column", "kind", "issue_prevented", "row_num", "rule"]
    )


def validate(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parts = [
        validate_table(t, frames[t], frames, strict=True)
        for t in sorted({c.table for c in CHECKS})
        if t in frames
    ]
    return pd.concat(parts, ignore_index=True) if parts else validate_table("", pd.DataFrame())


def catch_report(frames: dict[str, pd.DataFrame], violations: pd.DataFrame | None = None) -> pd.DataFrame:
    """For each check: how many existing rows it would have rejected, and which issue that prevents."""
    v = validate(frames) if violations is None else violations
    counts = v.groupby("check_id")["row_num"].nunique() if len(v) else pd.Series(dtype=int)
    rows = [
        {
            "check_id": c.id,
            "table": c.table,
            "column": c.column,
            "kind": c.kind,
            "issue_prevented": c.issue,
            "rule": c.description,
            "rows_in_table": int(len(frames[c.table])) if c.table in frames else 0,
            "rows_it_would_reject": int(counts.get(c.id, 0)),
        }
        for c in CHECKS
    ]
    return pd.DataFrame(rows)
