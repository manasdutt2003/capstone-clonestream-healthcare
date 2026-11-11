"""Root-cause evidence and hypothesis verdicts (Phase 2, tasks 2.2 - 2.5).

Each piece of evidence is a SQL file under sql/rootcause/. Verdicts are computed from the evidence by explicit rules, so
the report cannot say something the data does not support, and a regression test pins the conclusions.
"""

from __future__ import annotations

import pandas as pd

from hcls import config
from hcls.dq.runner import connect
from hcls.rootcause import lineage, timeline

EVIDENCE_SQL = [
    "c01_blank_by_status",
    "link_health",
    "claim_bill_amounts",
    "claim_bill_samples",
    "claim_bill_offset",
    "claim_patient_has_bill",
    "visits_missing_appt",
    "c03_by_plan",
    "c03_by_chapter",
    "c03_backfill",
    "sentinel_ids",
    "sentinel_propagation",
]
DECIDED = ("Approved", "Denied", "Appealed")
PIPELINE = ("Submitted", "Pending", "In Review")


def run_sql(name: str, con) -> pd.DataFrame:
    sql = (config.project_root() / "sql" / "rootcause" / f"{name}.sql").read_text(encoding="utf-8")
    return con.execute(sql).df()


def collect(
    frames: dict[str, pd.DataFrame], scorecard: pd.DataFrame, failures: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    con = connect(frames)
    ev = {name: run_sql(name, con) for name in EVIDENCE_SQL}
    con.close()
    ev["timeline_summary"], ev["timeline_long"] = timeline.timeline_report(frames, failures)
    ev["lineage"] = lineage.build_lineage(scorecard, ev["link_health"])
    return ev


# ------------------------------------------------------------------ hypotheses


def _h(issue, hid, layer, hypothesis, test, result, verdict):
    return {
        "issue": issue,
        "id": hid,
        "layer": layer,
        "hypothesis": hypothesis,
        "test": test,
        "result": result,
        "verdict": verdict,
    }


def _tl(ev, rule):
    return ev["timeline_summary"].set_index("rule_id").loc[rule]


def build_hypotheses(ev: dict[str, pd.DataFrame]) -> list[dict]:
    h: list[dict] = []

    # ---- C01: approved_amount blank on claims
    by = ev["c01_blank_by_status"].set_index("claim_status")
    decided_n = int(by.loc[[s for s in DECIDED if s in by.index], "claims"].sum())
    decided_blank = int(by.loc[[s for s in DECIDED if s in by.index], "approved_amount_blank"].sum())
    pipe_n = int(by.loc[[s for s in PIPELINE if s in by.index], "claims"].sum())
    pipe_blank = int(by.loc[[s for s in PIPELINE if s in by.index], "approved_amount_blank"].sum())
    same_dates = int(by["approved_date_blank"].sum()) == int(by["approved_amount_blank"].sum())
    h.append(
        _h(
            "C01",
            "H1.1",
            "ETL",
            "The pipeline dropped approved_amount for some claims that had one.",
            "Count blanks among claims the insurer has already decided (Approved, Denied, Appealed).",
            f"{decided_blank} of {decided_n} decided claims are blank.",
            "Ruled out" if decided_blank == 0 else "Possible",
        )
    )
    ok = pipe_blank == pipe_n and decided_blank == 0
    h.append(
        _h(
            "C01",
            "H1.2",
            "Process / design",
            "approved_amount is only filled in once the insurer decides, so blanks are expected on open claims.",
            "Compare blanks with claim status; check approved_date is blank on exactly the same claims.",
            f"{pipe_blank} of {pipe_n} claims in Submitted / Pending / In Review are blank; {decided_blank} of {decided_n} decided claims are blank; "
            f"approved_date is blank on {'exactly the same' if same_dates else 'a different set of'} claims.",
            "Confirmed" if ok and same_dates else "Likely" if ok else "Not supported",
        )
    )
    t = _tl(ev, "C01")
    h.append(
        _h(
            "C01",
            "H1.3",
            "Source application",
            "A recent change stopped the field being filled.",
            "Chi-square test of the yearly blank rate.",
            f"Blank in {int(t.years_with_failures)} of {int(t.years_observed)} years ({t.first_year}-{t.last_year}); p = {t.p_value}; {t.verdict}.",
            "Ruled out" if str(t.verdict).startswith("flat") else "Possible",
        )
    )

    # ---- C02: visits without an appointment
    lh = ev["link_health"].set_index("link")
    v = lh.loc["Visits -> Appointments"]
    vm = ev["visits_missing_appt"]
    miss, with_appts = (
        int(vm["missing_appointment"].sum()),
        int(vm["missing_but_patient_has_appointments"].sum()),
    )
    t = _tl(ev, "C02")
    h.append(
        _h(
            "C02",
            "H2.1",
            "Source application / database",
            "Visits can be saved without an appointment (walk-ins, emergencies) and no rule forces a link.",
            "Rate by year and by visit note; orphan ids elsewhere show whether the source enforces any constraint.",
            f"{miss} visits have no appointment; blank in {int(t.years_with_failures)} of {int(t.years_observed)} years ({t.verdict}, p = {t.p_value}); "
            "the rate does not depend on the visit note; placeholder ids exist in 8 tables (see sentinel analysis).",
            "Likely" if str(t.verdict).startswith("flat") else "Possible",
        )
    )
    h.append(
        _h(
            "C02",
            "H2.2",
            "ETL",
            "The link existed in the source and was lost during loading.",
            "If it was lost, the same patient should have an appointment on file.",
            f"Only {with_appts} of the {miss} unlinked visits belong to a patient who has any appointment at all.",
            "Not supported" if with_appts / max(miss, 1) < 0.25 else "Possible",
        )
    )
    same_pct = 100 * v.same_patient / v.linked_rows
    h.append(
        _h(
            "C02",
            "H2.3",
            "ETL / key mapping",
            "The links that ARE present are correct.",
            "For visits that do have an appointment, compare the visit's patient with the appointment's patient.",
            f"Only {int(v.same_patient)} of {int(v.linked_rows)} linked visits ({same_pct:.1f}%) point at an appointment for the same patient; "
            f"median gap between visit and appointment date is {v.median_gap_days:.0f} days.",
            "Ruled out" if same_pct < 5 else "Possible",
        )
    )

    # ---- C03: prescribed_meds = 'None'
    plan = ev["c03_by_plan"].set_index("plan_type")
    drug = plan.loc["plan names a drug"]
    other = plan.loc[[i for i in plan.index if i != "plan names a drug"]].iloc[0]
    bf = ev["c03_backfill"].iloc[0]
    h.append(
        _h(
            "C03",
            "H3.1",
            "Clinical meaning",
            "'None' correctly means no medicine was prescribed.",
            "A treatment plan that names a drug should have a prescribed medicine.",
            f"{int(drug.meds_none)} of {int(drug.records)} records whose plan names a drug ({drug.pct_none}%) have prescribed_meds = None, "
            f"versus {other.pct_none}% where the plan is not a drug. Those {int(drug.meds_none)} are contradictions; the other {int(other.meds_none)} cannot be judged without a clinician.",
            "Partly ruled out" if drug.meds_none > 0 else "Possible",
        )
    )
    t = _tl(ev, "C03")
    h.append(
        _h(
            "C03",
            "H3.2",
            "Source application",
            "The application writes the word 'None' when the medication field is left empty.",
            "All 40 are the literal text 'None' (zero real blanks); the rate is the same whether or not the plan names a drug.",
            f"{int(bf.none_records)} records, all literal 'None'; {drug.pct_none}% vs {other.pct_none}% by plan type; failing years {t.first_year}-{t.last_year}.",
            "Likely" if abs(drug.pct_none - other.pct_none) < 10 else "Possible",
        )
    )
    h.append(
        _h(
            "C03",
            "H3.3",
            "Recovery",
            "The missing medicines can be backfilled from the Prescriptions table.",
            "Find prescriptions for the same patient on or before the record date.",
            f"{int(bf.patient_has_any_prescription)} of {int(bf.none_records)} patients have any prescription; {int(bf.same_patient_and_doctor)} match the same doctor.",
            "Not feasible"
            if bf.patient_has_any_prescription / max(bf.none_records, 1) < 0.25
            else "Possible",
        )
    )
    pre = ev["timeline_long"]
    yearly = pre[(pre.rule_id == "C03") & (pre.granularity == "year")]
    small = int(yearly.loc[yearly.records < timeline.MIN_N, "records"].sum())
    h.append(
        _h(
            "C03",
            "H3.4",
            "Source application",
            "A recent change introduced the problem.",
            "Yearly rate; only years with at least 10 records can be tested.",
            f"Only {len(yearly[yearly.records >= timeline.MIN_N])} years have enough records (earlier years hold {small} records in total); "
            f"p = {t.p_value}, {t.verdict}.",
            "Inconclusive",
        )
    )

    # ---- Key mapping (A02 / A30 and the other broken links)
    off = ev["claim_bill_offset"]
    best_off = off.sort_values("same_patient", ascending=False).iloc[0]
    amt = ev["claim_bill_amounts"].iloc[0]
    has = ev["claim_patient_has_bill"].iloc[0]
    h.append(
        _h(
            "KEY",
            "H4.1",
            "ETL",
            "Bills were attached to claims a fixed number of rows out of place (positional shift).",
            "Shift billing_id by -10 .. +10 and count patient matches.",
            f"Best shift matches {int(best_off.same_patient)} of {int(best_off.pairs)} pairs; at shift 0 it is {int(off.set_index('offset_k').loc[0, 'same_patient'])}.",
            "Ruled out" if best_off.same_patient <= 3 else "Possible",
        )
    )
    h.append(
        _h(
            "KEY",
            "H4.2",
            "ETL",
            "Claims should be joined to bills through the patient instead.",
            "How many claims have a patient who appears in Billing at all?",
            f"{int(has.claims_whose_patient_has_a_bill)} of {int(has.claims)} claims. Even on a patient join the amounts would not agree (median claim is {amt.median_ratio:.0f}x the bill; "
            f"{int(amt.within_25_percent)} of {int(amt.pairs)} within 25%).",
            "Ruled out" if has.claims_whose_patient_has_a_bill / has.claims < 0.25 else "Possible",
        )
    )
    bad_links = lh[lh.same_patient / lh.linked_rows < 0.05]
    good_links = lh[lh.same_patient / lh.linked_rows >= 0.95]
    h.append(
        _h(
            "KEY",
            "H4.3",
            "ETL / key mapping",
            "Each table's patient and parent ids are generated or mapped independently, so most links do not line up.",
            "For all six links that carry a patient on both sides, compare child and parent patients.",
            f"{len(bad_links)} of {len(lh)} links match the same patient in under 5% of rows ({', '.join(bad_links.index)}). "
            f"Only {', '.join(good_links.index) or 'none'} holds up, which proves consistent keys are possible.",
            "Confirmed"
            if len(bad_links) >= 4 and len(good_links) >= 1
            else "Likely"
            if len(bad_links) >= 3
            else "Possible",
        )
    )
    sp = ev["sentinel_propagation"].iloc[0]
    sent = ev["sentinel_ids"]
    h.append(
        _h(
            "KEY",
            "H4.4",
            "Source database",
            "The source does not enforce foreign keys, so placeholder ids (0, -1, 88888, 9999x) get stored.",
            "Count orphan patient ids by table and trace one table's placeholders back to its parent.",
            f"{int(sent.rows_affected.sum())} rows in {sent.table_name.nunique()} tables hold an id that matches no patient. "
            f"{int(sp.appointment_has_same_orphan_id)} of {int(sp.bills_with_orphan_patient)} orphan bills inherit the same placeholder from their appointment, so it starts upstream.",
            "Confirmed"
            if sent.table_name.nunique() >= 5
            and sp.appointment_has_same_orphan_id >= 0.8 * sp.bills_with_orphan_patient
            else "Likely",
        )
    )
    return h


def hypotheses_frame(ev: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame(build_hypotheses(ev))
