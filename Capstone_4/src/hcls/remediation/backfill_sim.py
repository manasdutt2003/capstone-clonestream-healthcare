"""Backfill simulation (Phase 4, task 4.2). Runs on a COPY of the cleaned data; the source frames are never changed.

C03  prescribed_meds missing  <- Prescriptions (same patient, prescription active on the record date, ideally the same doctor)
C02  visit without appointment <- Appointments (same patient, appointment date within one day of the visit)

Only unambiguous, high-confidence matches are applied to the copy. Everything else is listed for a person to decide.
Nothing is invented: a value is copied from another record or left blank (DECISIONS D-009).
"""

from __future__ import annotations

import pandas as pd

from hcls.dq import rules as dq_rules
from hcls.dq import runner
from hcls.remediation.common import blank, date, num

DRUG_PLANS = {  # treatment plans that name a drug (same list as sql/rootcause/c03_by_plan.sql)
    "Atorvastatin 20mg": "Atorvastatin",
    "Albuterol": "Albuterol",
    "Levothyroxine": "Levothyroxine",
    "Lisinopril 10mg": "Lisinopril",
    "Metformin 500mg": "Metformin",
    "Ibuprofen 400mg": "Ibuprofen",
    "Sertraline 50mg": "Sertraline",
    "Amoxicillin 500mg": "Amoxicillin",
    "Omeprazole 20mg": "Omeprazole",
}
APPLY_C03 = {"High", "Medium"}
APPLY_C02 = {"High"}
DAY_WINDOW = 1
KNOWN = ("High", "Medium", "Low", "Ambiguous", "Conflict")


def fingerprint(frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """A content hash per table, used to prove the source was not touched."""
    return {k: int(pd.util.hash_pandas_object(v.astype(str), index=True).sum()) for k, v in frames.items()}


# ------------------------------------------------------------------ C03


def propose_c03(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    mr, rx = frames["Medical_Records"], frames["Prescriptions"].copy()
    rx["_pid"] = num(rx["patient_id"])
    rx["_start"], rx["_end"] = date(rx["start_date"]), date(rx["end_date"])
    rx["_doc"] = num(rx["doctor_id"])
    rows = []
    for rec in mr[blank(mr["prescribed_meds"])].to_dict("records"):
        pid = num(pd.Series([rec["patient_id"]])).iloc[0]
        rdate = date(pd.Series([rec["record_date"]])).iloc[0]
        doc = num(pd.Series([rec["doctor_id"]])).iloc[0]
        mine = rx[rx["_pid"] == pid] if pd.notna(pid) else rx.iloc[0:0]
        active = (
            mine[(mine["_start"] <= rdate) & (mine["_end"].isna() | (mine["_end"] >= rdate))]
            if pd.notna(rdate)
            else mine.iloc[0:0]
        )
        same_doc = active[active["_doc"] == doc]
        if len(same_doc):
            conf, src = "High", same_doc
        elif len(active):
            conf, src = "Medium", active
        elif len(mine):
            conf, src = "Low", mine
        else:
            conf, src = "None", mine
        value = ", ".join(sorted(set(src["medication_name"].dropna()))) if len(src) else ""
        plan = rec.get("treatment_plan")
        hint = DRUG_PLANS.get(plan, "")
        if conf in APPLY_C03 and hint and hint.lower() not in value.lower():
            conf = (
                "Conflict"  # the plan names a different drug: a clinician must decide which record is right
            )
        rows.append(
            {
                "record_id": rec["record_id"],
                "patient_id": rec["patient_id"],
                "record_date": rec["record_date"],
                "treatment_plan": plan,
                "prescriptions_for_patient": int(len(mine)),
                "active_on_record_date": int(len(active)),
                "same_doctor": int(len(same_doc)),
                "confidence": conf,
                "proposed_value": value,
                "plan_drug_hint": hint,
                "applied": conf in APPLY_C03,
                "source_row": rec["_row_num"],
            }
        )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ C02


def propose_c02(frames: dict[str, pd.DataFrame], window: int = DAY_WINDOW) -> pd.DataFrame:
    visits, ap = frames["Visits"], frames["Appointments"].copy()
    ap["_pid"], ap["_d"] = num(ap["patient_id"]), date(ap["appointment_date"])
    rows = []
    for v in visits[blank(visits["appointment_id"])].to_dict("records"):
        pid, vdate = num(pd.Series([v["patient_id"]])).iloc[0], date(pd.Series([v["visit_date"]])).iloc[0]
        valid = pd.notna(pid) and pid > 0 and pd.notna(vdate)
        cand = (
            ap[(ap["_pid"] == pid) & ((ap["_d"] - vdate).abs() <= pd.Timedelta(days=window))]
            if valid
            else ap.iloc[0:0]
        )
        has_any = int((ap["_pid"] == pid).sum()) if valid else 0
        conf = "High" if len(cand) == 1 else ("Ambiguous" if len(cand) > 1 else "None")
        rows.append(
            {
                "visit_id": v["visit_id"],
                "patient_id": v["patient_id"],
                "visit_date": v["visit_date"],
                "patient_has_any_appointment": has_any,
                "candidates": int(len(cand)),
                "confidence": conf if valid else "Not matchable (placeholder or missing patient/date)",
                "proposed_appointment_id": str(cand.iloc[0]["appointment_id"]) if len(cand) == 1 else "",
                "candidate_status": str(cand.iloc[0]["status"]) if len(cand) == 1 else "",
                "applied": conf == "High" and bool(valid),
                "source_row": v["_row_num"],
            }
        )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ simulation


def _failed(frames: dict[str, pd.DataFrame], ids: tuple[str, ...]) -> dict[str, int]:
    chosen = [r for r in dq_rules.build_rules(runner.table_columns(frames)) if r.id in ids]
    res, _, _ = runner.run_rules(frames, rules=chosen)
    return res.set_index("rule_id")["rows_failed"].astype(int).to_dict()


def simulate(frames: dict[str, pd.DataFrame]) -> dict:
    """Propose, apply to a deep copy, re-run the rules, and prove the source did not change."""
    before_fp = fingerprint(
        {k: frames[k] for k in ("Medical_Records", "Visits", "Prescriptions", "Appointments")}
    )
    c03, c02 = propose_c03(frames), propose_c02(frames)
    copy = {k: v.copy(deep=True) for k, v in frames.items()}
    fill = c03[c03["applied"]].set_index("record_id")["proposed_value"].to_dict()
    mr = copy["Medical_Records"]
    mask = mr["record_id"].isin(fill)
    mr.loc[mask, "prescribed_meds"] = mr.loc[mask, "record_id"].map(fill)
    link = c02[c02["applied"]].set_index("visit_id")["proposed_appointment_id"].to_dict()
    vs = copy["Visits"]
    vmask = vs["visit_id"].isin(link)
    vs.loc[vmask, "appointment_id"] = vs.loc[vmask, "visit_id"].map(link)
    rules_before = _failed(frames, ("C02", "C03"))
    rules_after = _failed(copy, ("C02", "C03"))
    after_fp = fingerprint(
        {k: frames[k] for k in ("Medical_Records", "Visits", "Prescriptions", "Appointments")}
    )
    if before_fp != after_fp:
        raise RuntimeError("backfill simulation changed the source data")
    rows = []
    for rule, label, prop in (
        ("C03", "prescribed_meds from Prescriptions", c03),
        ("C02", "appointment_id from Appointments", c02),
    ):
        total = len(prop)
        counts = prop["confidence"].value_counts()
        rows.append(
            {
                "rule_id": rule,
                "backfill": label,
                "records_failing_before": rules_before[rule],
                "proposals_high": int(counts.get("High", 0)),
                "proposals_medium": int(counts.get("Medium", 0)),
                "proposals_low_or_ambiguous": int(counts.get("Low", 0) + counts.get("Ambiguous", 0)),
                "conflicts_with_plan": int(counts.get("Conflict", 0)),
                "no_match": int(total - sum(int(counts.get(k, 0)) for k in KNOWN)),
                "applied_to_copy": int(prop["applied"].sum()),
                "records_failing_after": rules_after[rule],
                "recovered_pct": round(
                    100 * (rules_before[rule] - rules_after[rule]) / max(1, rules_before[rule]), 1
                ),
                "source_unchanged": True,
            }
        )
    return {"summary": pd.DataFrame(rows), "c03": c03, "c02": c02, "copy": copy}
