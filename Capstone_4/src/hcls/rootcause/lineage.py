"""Table-to-table lineage with link health (Phase 2, task 2.6).

Every foreign-key relationship becomes an edge. An edge's health combines two things:
  * orphan rate : child values with no matching parent row (rule R-*)
  * wrong-patient rate : for links that exist, how often the child and parent belong to different patients (link health SQL)
The source-system grouping is a HYPOTHESIS drawn from how the tables relate; the ETL owner must confirm it.
"""

from __future__ import annotations

import pandas as pd

from hcls.dq.rules import FOREIGN_KEYS

SOURCE_GROUP = {
    "Patients": "Registration / EHR",
    "Appointments": "Registration / EHR",
    "Visits": "Registration / EHR",
    "Medical_Records": "Registration / EHR",
    "Admissions": "Registration / EHR",
    "Patient_Procedures": "Registration / EHR",
    "Referrals": "Registration / EHR",
    "Prescriptions": "Pharmacy",
    "Prescription_Administration": "Pharmacy",
    "Billing": "Billing & Claims",
    "Insurance_Claims": "Billing & Claims",
    "Patient_Insurance": "Billing & Claims",
    "Doctors": "Organisation & Staff",
    "Nurses": "Organisation & Staff",
    "Nurse_Assignments": "Organisation & Staff",
    "Hospitals": "Organisation & Staff",
    "Departments": "Organisation & Staff",
    "Hierarchy": "Organisation & Staff",
    "Procedure_Codes": "Reference data",
}
# link_health.sql label -> (child table, child column)
LINK_LABELS = {
    "Visits -> Appointments": ("Visits", "appointment_id"),
    "Medical_Records -> Appointments": ("Medical_Records", "appointment_id"),
    "Billing -> Appointments": ("Billing", "appointment_id"),
    "Insurance_Claims -> Billing": ("Insurance_Claims", "billing_id"),
    "Patient_Insurance -> Insurance_Claims": ("Patient_Insurance", "claim_id"),
    "Prescription_Administration -> Prescriptions": ("Prescription_Administration", "prescription_id"),
}
GREEN_BELOW, RED_AT = 1.0, 10.0  # percent


def status_of(bad_pct: float) -> str:
    return "healthy" if bad_pct < GREEN_BELOW else ("degraded" if bad_pct < RED_AT else "broken")


def build_lineage(scorecard: pd.DataFrame, link_health: pd.DataFrame) -> pd.DataFrame:
    sc = scorecard.set_index("rule_id")
    wrong = {}
    for r in link_health.itertuples():
        wrong[LINK_LABELS[r.link]] = 100 * (1 - r.same_patient / r.linked_rows) if r.linked_rows else None
    rows = []
    for child, col, parent, pcol in FOREIGN_KEYS:
        rid = f"R-{child}-{col}"
        orphan = float(sc.loc[rid, "pct_failed"]) if rid in sc.index else 0.0
        wp = wrong.get((child, col))
        bad = max(orphan, wp or 0.0)
        rows.append(
            {
                "child_table": child,
                "child_column": col,
                "parent_table": parent,
                "parent_column": pcol,
                "orphan_pct": round(orphan, 2),
                "wrong_patient_pct": None if wp is None else round(wp, 1),
                "status": status_of(bad),
                "child_group": SOURCE_GROUP[child],
                "parent_group": SOURCE_GROUP[parent],
                "crosses_systems": SOURCE_GROUP[child] != SOURCE_GROUP[parent],
            }
        )
    return pd.DataFrame(rows)


def to_mermaid(lineage: pd.DataFrame) -> str:
    """A Mermaid flowchart: one box per table (grouped by hypothesised source system), one arrow per foreign key."""
    lines = ["flowchart LR"]
    groups: dict[str, set[str]] = {}
    for t, g in SOURCE_GROUP.items():
        groups.setdefault(g, set()).add(t)
    for g, tabs in groups.items():
        gid = "".join(ch for ch in g.title() if ch.isalnum())
        lines.append(f'  subgraph {gid}["{g}"]')
        lines += [f"    {t}[{t}]" for t in sorted(tabs)]
        lines.append("  end")
    colors = {"healthy": "#2e7d32", "degraded": "#ef6c00", "broken": "#c62828"}
    styles = []
    for idx, e in enumerate(lineage.itertuples()):
        label = e.status if pd.isna(e.wrong_patient_pct) else f"wrong patient {e.wrong_patient_pct:.0f}%"
        if (
            e.status != "healthy"
            and not pd.isna(e.orphan_pct)
            and e.orphan_pct >= 1
            and pd.isna(e.wrong_patient_pct)
        ):
            label = f"orphans {e.orphan_pct:.0f}%"
        if e.status == "healthy":
            lines.append(f"  {e.child_table} --> {e.parent_table}")
        else:
            lines.append(f'  {e.child_table} -->|"{e.child_column}: {label}"| {e.parent_table}')
        styles.append(f"  linkStyle {idx} stroke:{colors[e.status]},stroke-width:2px")
    return "\n".join(lines + styles)
