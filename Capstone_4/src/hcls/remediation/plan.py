"""Remediation matrix and the generated remediation plan (Phase 4, tasks 4.1 and 4.7).

The matrix is data: one group per root cause, covering every Critical and High rule. A test fails if the scorecard has a
Critical or High finding that no group covers, so the plan cannot silently fall behind the data.
Effort is a planning estimate (S < 1 day, M 1-3 days, L 1-2 weeks) for the owner to confirm.
"""

from __future__ import annotations

import pandas as pd

from hcls import config
from hcls.reports import md_table

PATIENT_FK = [
    f"R-{t}-patient_id"
    for t in (
        "Visits",
        "Medical_Records",
        "Billing",
        "Prescription_Administration",
        "Appointments",
        "Prescriptions",
        "Referrals",
        "Admissions",
    )
]

MATRIX = [
    {
        "id": "G1",
        "title": "Approved amount blank on open claims (C01)",
        "rules": ["C01"],
        "action": "Accept as by-design",
        "what": "Report the 90 blanks as pipeline (estimated). Label the field 'pending decision' so a blank is never read as lost data.",
        "owner": "Finance + Claims team",
        "effort": "S",
        "risk": "Low",
        "rollback": "None needed: no data is changed.",
        "prevent": ["V-C01"],
    },
    {
        "id": "G2",
        "title": "Broken links between tables (A02, A30, A38, A03, A01)",
        "rules": ["A02", "A30", "A38", "A03", "A01"],
        "action": "Fix at source, quarantine until fixed",
        "what": "Conform patient, bill, claim and prescription keys at the ETL mapping step; add foreign keys with a same-patient check. Until fixed, never join claims to bills (D-004).",
        "owner": "ETL owner",
        "effort": "L",
        "risk": "High",
        "rollback": "Keep the old key column beside the new one for two releases; version the mapping table; re-run reconciliation before and after.",
        "prevent": [
            "V-LINK-Insurance_Claims-billing_id",
            "V-LINK-Patient_Insurance-claim_id",
            "V-LINK-Prescription_Administration-prescription_id",
            "V-A01",
        ],
    },
    {
        "id": "G3",
        "title": "Visits without an appointment (C02)",
        "rules": ["C02"],
        "action": "Fix at source; backfill not viable",
        "what": "Make the appointment reference mandatory, or add an explicit walk-in type. The matching simulation recovers none of the 123, so a clerical review of the source is the only route for history.",
        "owner": "Registration / EHR owner",
        "effort": "M",
        "risk": "Medium",
        "rollback": "Feature-flag the new constraint; load in warn-only mode for one week first.",
        "prevent": ["V-C02"],
    },
    {
        "id": "G4",
        "title": "Medical records with prescribed_meds = None (C03)",
        "rules": ["C03"],
        "action": "Clinician review, then fix at source",
        "what": "The simulation applies no automatic fill: of 40, one has only an inactive prescription and two conflict with the treatment plan. 20 name a drug in the plan, so those go to the clinician first. Add an explicit 'no medication' code.",
        "owner": "Clinical owner",
        "effort": "M",
        "risk": "Medium",
        "rollback": "Write corrections to a separate table with a reviewer id; never overwrite the original value.",
        "prevent": ["V-C03"],
    },
    {
        "id": "G5",
        "title": "Placeholder and orphan ids, duplicate patients",
        "rules": [*PATIENT_FK, "R-Medical_Records-appointment_id", "R-Billing-appointment_id", "A16"],
        "action": "Quarantine, then enforce foreign keys",
        "what": "Move rows with placeholder patient ids (0, negative, 88888, 9999x) to a quarantine table for resolution; add FK constraints; review the duplicate patient ids for a merge.",
        "owner": "Registration / EHR owner + ETL owner",
        "effort": "M",
        "risk": "Medium",
        "rollback": "Quarantine is a move with a log of original positions, so a restore script puts rows back.",
        "prevent": ["V-SENT-Visits", "V-FK-Visits-patient_id", "V-A16"],
    },
    {
        "id": "G6",
        "title": "Dates out of order (A24, A28)",
        "rules": ["A24", "A28"],
        "action": "Flag, then correct at source",
        "what": "Discharge before admission (152) and prescription end before start (118) cannot be repaired by swapping dates (that is a guess, D-012). Flag, route to the owning team, add date-order checks.",
        "owner": "Clinical operations",
        "effort": "M",
        "risk": "Low",
        "rollback": "Corrections go in an adjustment table; originals stay.",
        "prevent": ["V-A24", "V-A28"],
    },
    {
        "id": "G7",
        "title": "Billing and claim amounts (A09, A10, A11, A44, A07)",
        "rules": ["A09", "A10", "A11", "A44", "A07"],
        "action": "Quarantine (hold) and review",
        "what": "Negative totals, approved above submitted, paid above responsibility and totals that do not add up are held out of reconciliation (as the 4 DQ Hold claims already are) and reviewed by Finance.",
        "owner": "Finance + Billing system owner",
        "effort": "S",
        "risk": "Low",
        "rollback": "Held rows stay in place and are only labelled; release them by clearing the flag.",
        "prevent": ["V-A07", "V-A44", "V-A11", "V-A09", "V-A10"],
    },
    {
        "id": "G8",
        "title": "Administered unit differs from prescribed unit (A31)",
        "rules": ["A31"],
        "action": "Defer until G2 is fixed",
        "what": "The administration row points at a prescription of a different patient (A30), so the unit comparison is meaningless today. Re-test after the key fix; then standardise units.",
        "owner": "Pharmacy / Clinical owner",
        "effort": "S",
        "risk": "Low",
        "rollback": "None needed: no data is changed.",
        "prevent": ["V-LINK-Prescription_Administration-prescription_id"],
    },
    {
        "id": "G9",
        "title": "Bills raised for Cancelled or No-Show appointments (A12)",
        "rules": ["A12"],
        "action": "Compliance review",
        "what": "81 of 249 bills sit on appointments that did not take place. This could be real over-billing or the broken link again. Compliance to review a sample against the source system.",
        "owner": "Compliance",
        "effort": "M",
        "risk": "High",
        "rollback": "Review only; no data is changed. Any refund waits for the answer to the over-charging question.",
        "prevent": ["V-A12"],
    },
]


def covered_rules() -> set[str]:
    return {r for g in MATRIX for r in g["rules"]}


def uncovered(scorecard: pd.DataFrame) -> list[str]:
    hi = scorecard[scorecard["severity"].isin(["Critical", "High"]) & (scorecard["rows_failed"] > 0)]
    return sorted(set(hi["rule_id"]) - covered_rules())


JOBS = [
    (
        "dq_daily",
        "Every day 02:00 UTC",
        "ingest, clean, dq, alerts",
        "Data-quality scorecard and alerts",
        "30 min",
    ),
    (
        "recon_weekly",
        "Mondays 06:00 UTC",
        "ingest, clean, recon",
        "Finance reconciliation workbook and brief",
        "10 min (SLA alert at 5)",
    ),
    (
        "audit_nightly",
        "Every day 03:00 UTC",
        "all, alerts",
        "Full rebuild of every output for the audit trail",
        "45 min",
    ),
]

SIGNOFF = [
    "Staging evidence: `python -m hcls all` run on a copy of production data; scorecard, reconciliation tie-out and alert file attached.",
    "Backfill and quarantine steps run on a copy first; before and after counts match the simulation report.",
    "Rollback tested: the restore step was run once in staging and the row counts returned to the originals.",
    "Validators run in warn-only mode for one week before they start rejecting rows.",
    "Monitoring in place: daily scorecard job, alert recipients confirmed (Finance for Critical rules).",
    "Owners named and effort accepted for every group in the matrix.",
    "Approval recorded in GitHub (`production` environment reviewer) before any deploy.",
]


def render_plan(
    scorecard: pd.DataFrame,
    sim: pd.DataFrame,
    catch: pd.DataFrame,
    violations: pd.DataFrame,
    alerts: dict,
    run_label: str,
) -> str:
    hi = scorecard[
        scorecard["severity"].isin(["Critical", "High"]) & (scorecard["rows_failed"] > 0)
    ].sort_values("rank")
    group_of = {r: g["id"] for g in MATRIX for r in g["rules"]}
    s = sim.set_index("rule_id")
    rejected_rows = (
        violations.groupby("table")["row_num"].nunique().sort_values(ascending=False)
        if len(violations)
        else pd.Series(dtype=int)
    )
    by_issue = catch.groupby("issue_prevented")["rows_it_would_reject"].max().sort_values(ascending=False)
    cnt = alerts.get("counts", {})
    out = [
        "# Remediation and Prevention Plan",
        "",
        f"*Generated by `python -m hcls docs` ({run_label}). As-of date {config.as_of_date().isoformat()}. Evidence comes from `outputs/gold/` (scorecard, backfill simulation, validator report, alerts). Effort figures are planning estimates for the owner to confirm. Do not edit by hand.*",
        "",
        "## 1. The plan in plain language",
        "",
        f"- **{len(hi)} Critical and High findings, grouped into {len(MATRIX)} root causes.** Each has an owner, an action, a risk and a rollback (section 2). None is left without a plan (section 3).",
        f"- **Backfill will not repair history.** On a copy, matching recovers **{int(s.loc['C03', 'applied_to_copy'])} of {int(s.loc['C03', 'records_failing_before'])}** missing medicines and **{int(s.loc['C02', 'applied_to_copy'])} of {int(s.loc['C02', 'records_failing_before'])}** unlinked visits. The source was verified unchanged. The fix is at the source, plus clinician and clerical review.",
        f"- **Validators would have blocked the problems at entry.** {len(catch)} checks, each tied to the issue it prevents (section 5).",
        f"- **Monitoring is defined.** Latest run: **{alerts.get('status', 'n/a')}**, {len(alerts.get('alerts', []))} alerts ({', '.join(f'{v} {k}' for k, v in cnt.items()) or 'none'}).",
        "- **Nothing here is deployed to production.** The Databricks jobs and the deploy workflow are defined and dry-run only; a human approval gate sits in front of any release (section 6).",
        "",
        "## 2. Remediation matrix",
        "",
        "| # | Issue | Action | Owner | Effort | Risk | Rollback |",
        "|---|---|---|---|---|---|---|",
    ]
    for g in MATRIX:
        out.append(
            f"| {g['id']} | {g['title']} | **{g['action']}**. {g['what']} | {g['owner']} | {g['effort']} | {g['risk']} | {g['rollback']} |"
        )
    out += [
        "",
        "## 3. Every Critical and High finding has a plan",
        "",
        "| Rank | Rule | Table | Severity | Failing | Group |",
        "|---:|---|---|---|---:|---|",
    ]
    for r in hi.itertuples():
        out.append(
            f"| {int(r.rank)} | {r.rule_id} | {r.table} | {r.severity} | {int(r.rows_failed)} of {int(r.rows_checked)} | {group_of.get(r.rule_id, 'NOT COVERED')} |"
        )
    out += [
        "",
        "## 4. Backfill simulation (on a copy; the source is never changed)",
        "",
        "C03 is filled from Prescriptions (same patient, prescription active on the record date, same doctor = High, different doctor = Medium). A match is rejected if the treatment plan names a different drug. C02 is matched to an appointment for the same patient within one day. Only High (C02) and High or Medium (C03) are applied.",
        "",
        md_table(sim, [c for c in sim.columns if c != "backfill"]),
        "",
        "What the numbers mean:",
        "",
        f"- **C03:** only {int(s.loc['C03', 'proposals_low_or_ambiguous'] + s.loc['C03', 'conflicts_with_plan'])} of {int(s.loc['C03', 'records_failing_before'])} records have any prescription candidate at all, and none is both consistent and from the same doctor. {int(s.loc['C03', 'conflicts_with_plan'])} candidates contradict the treatment plan, so applying them would put a wrong drug on a record.",
        f"- **C02:** {int(s.loc['C02', 'no_match'])} of {int(s.loc['C02', 'records_failing_before'])} visits have no appointment for the same patient within a day. The patient ids themselves are unreliable (Sprint 2), which is why matching fails.",
        "- Row-level proposals: `outputs/gold/backfill_c03.csv`, `outputs/gold/backfill_c02.csv`.",
        "",
        "## 5. Prevention: ingest validators",
        "",
        f"`hcls.remediation.validators` holds {len(catch)} checks (not-null, foreign key, same-patient, placeholder id, unique, range, date order, enum, business rule). Run on the current data they reject:",
        "",
        md_table(
            by_issue.rename("rows_it_would_reject").reset_index(), ["issue_prevented", "rows_it_would_reject"]
        ),
        "",
        "Rows rejected by at least one check, per table:",
        "",
        md_table(rejected_rows.rename("rows").reset_index(), ["table", "rows"])
        if len(rejected_rows)
        else "none",
        "",
        "Full list: `outputs/gold/validator_catch.csv`. Rollout: warn-only for one week, then reject.",
        "",
        "## 6. Deployment and monitoring",
        "",
        "Databricks jobs (`databricks/jobs/`, notebooks in `databricks/notebooks/`):",
        "",
        "| Job | Schedule | Runs | Purpose | Time limit |",
        "|---|---|---|---|---|",
        *[f"| `{j}` | {sch} | {steps} | {why} | {lim} |" for j, sch, steps, why, lim in JOBS],
        "",
        "All jobs retry twice, time out, and email on failure. A run longer than 5 minutes on `recon_weekly` raises an alert.",
        "",
        "Pipeline (`.github/workflows`): 1 code quality, 2 unit tests, 3 data tests, 4 integration + coverage gate, **5 approval gate (`production` environment, required reviewer)**, 6 simulated deploy (dry-run of the job definitions, release artefacts). Stages 1-4 run on every pull request; 5-6 run only after a merge to main.",
        "",
        "Alerts (`outputs/alerts.json`): a Critical rule failing on more than 5% of records, a rule's failures moving by more than 10% between runs, reconciliation over 5 minutes.",
        "",
        "## 7. Senior data-engineer sign-off",
        "",
        *[f"- [ ] {x}" for x in SIGNOFF],
        "",
        "| Reviewer | Role | Date | Decision |",
        "|---|---|---|---|",
        "| | Senior data engineer | | |",
        "| | Finance owner | | |",
        "| | Compliance | | |",
        "",
        "## 8. Answers to Key Questions 5 and 8",
        "",
        "**5. Can we fix it?** Partly. C01 needs no fix (by design). The broken links need a source fix by the ETL owner. C02 and C03 cannot be backfilled from the data we have, only prevented from now on and reviewed by people. Placeholder ids and out-of-order dates go to quarantine and review.",
        "",
        "**8. How do we prevent it?** Ingest validators (section 5), database constraints (not null, foreign keys with a same-patient check), a daily data-quality job with alerts (section 6), and a data contract with the claims and registration systems.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "python -m hcls backfill && python -m hcls validate && python -m hcls alerts && python -m hcls docs",
        "```",
        "",
    ]
    return "\n".join(out)
