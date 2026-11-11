"""One-page, plain-language memos for Finance, Compliance and Patient Care (Phase 5, task 5.5).

Every number comes from `facts.collect`, so a memo cannot disagree with the data. No jargon, no rule codes in the body
(codes appear only in the 'where to look' line for the reader who wants to check).
"""

from __future__ import annotations

from hcls.audit.facts import usd
from hcls.remediation import plan


def _owner(group: str) -> str:
    return next(g["owner"] for g in plan.MATRIX if g["id"] == group)


def finance(f: dict) -> str:
    b, ev = f["bucket"], f["expected"]
    c01 = f["rule"]["C01"]
    return f"""# Memo for Finance: what we can count on

*As of {f["as_of"]}. Prepared for the CFO and the Finance team. Source: the claims table only.*

## The answer in three lines

1. **Counted and safe to report: {usd(b["Paid"]["amount"])}** paid on {b["Paid"]["claims"]} claims. The insurers reduced those claims by a further {usd(b["Adjustment"]["amount"])}, and denied {b["Denied"]["claims"]} claims worth {usd(b["Denied"]["amount"])}.
2. **Still to be decided: {usd(b["Pipeline"]["amount"])} asked on {b["Pipeline"]["claims"]} open claims.** We expect about **{usd(ev["expected"], True)}** to be approved (likely between {usd(ev["low"], True)} and {usd(ev["high"], True)}). The earlier Flash figure of {usd(ev["ceiling_no_denials"], True)} assumed no claim is ever denied, so treat it as the most it could be, not what to plan on.
3. **Held out for checking: {b["DQ Hold"]["claims"]} claims** have impossible amounts or payment dates. They are excluded from the paid figure until someone reviews them.

Every dollar is accounted for: the groups add up to {usd(f["submitted_total"])} submitted across {f["claims_total"]} claims.

## Please read before quoting a number

- **The {c01["rows"]} claims with no approved amount are not lost data.** They are claims the insurer has not decided yet. A blank is normal until then.
- **{f["pipeline_old"]} of the {f["pipeline_claims"]} open claims were submitted more than a year ago.** If they are no longer being chased, the expected figure is too high.
- **The brief's $2.3M and $1.8M cannot be reproduced** from the data. Use the figures above and say where they come from.
- **Dates cannot tell us when money arrived:** {f["paid_date_flagged"]} of the {f["paid_claims"]} paid claims have a date in the wrong order.

## Do not refund yet

We cannot say whether patients were over-charged. The link from each claim to its bill points at the wrong patient on {f["link_health"].loc["Insurance_Claims -> Billing", "linked_rows"] - f["link_health"].loc["Insurance_Claims -> Billing", "same_patient"]:.0f} of {f["link_health"].loc["Insurance_Claims -> Billing", "linked_rows"]:.0f} claims, so any comparison would look exact and be wrong. Hold refund decisions until the link is fixed and the check is re-run.

## What we need from Finance

1. Confirm the paid total against the insurer remittance or the bank.
2. Tell us whether the old open claims are still being worked.
3. Review the {b["DQ Hold"]["claims"]} held claims (list in the workbook, sheet *DQ Exceptions*).

*Where to look: `outputs/finance/CloneStream_Claims_Reconciliation_{f["as_of"]}.xlsx`, `docs/03_finance_brief.md`.*
"""


def compliance(f: dict) -> str:
    r = f["rule"]
    return f"""# Memo for Compliance: what the auditors will see

*As of {f["as_of"]}. Prepared for the Compliance lead ahead of Friday's audit.*

## The answer in three lines

1. **We ran {f["rules_run"]} checks across all {f["tables_total"]} tables and found problems in {f["findings"]}.** {f["critical_high"]} are serious ({f["severity"].get("Critical", 0)} critical, {f["severity"].get("High", 0)} high), spread over {f["tables_with_critical_high"]} tables.
2. **This is not a recent incident.** The share of bad records is about the same in every year from 2020 (no statistical evidence of a change). The system never stopped bad data going in.
3. **Nothing was deleted or invented.** The cleaned dataset has every original row. Money, doses and links are flagged, never changed, so the evidence is intact.

## The points auditors will ask about

| Question | What the data shows |
|---|---|
| Are visits linked to appointments? | **{r["C02"]["rows"]} of {r["C02"]["of"]} visits** ({r["C02"]["pct"]:.1f}%) have no appointment. |
| Do patient ids always exist? | **{f["sentinel_rows"]} records in {f["sentinel_tables"]} tables** carry placeholder ids (0, -1, 88888, 9999x). They start upstream, in the appointment system. |
| Were bills raised for visits that did not happen? | **{r["A12"]["rows"]} bills** are for cancelled or no-show appointments. This needs a compliance review: it may be a billing error. |
| Can dates be trusted? | {f["paid_date_flagged"]} of {f["paid_claims"]} paid claims have dates out of order. |
| Is there an audit trail? | Yes. Every pipeline run is logged with who, when, the code version, and a fingerprint of each output (`outputs/gold/audit_log.csv`). |

## What is being done

- **Fix at the source** (owners named in `docs/04_remediation_plan.md`). Repairing history is not possible: a simulated backfill recovered {int(f["backfill"].loc["C02", "applied_to_copy"])} of {int(f["backfill"].loc["C02", "records_failing_before"])} unlinked visits.
- **Stop it recurring:** {f["validators"]} checks would run when data is loaded. On this data they would have rejected {f["validator_rows"]:,} records. They start in warn-only mode.
- **Watch it daily:** a daily job raises an alert when a critical check fails on more than 5% of records. Today it raises {len(f["alerts"]["alerts"])}.

## What we need from Compliance

1. Review the {r["A12"]["rows"]} bills for cancelled or no-show appointments.
2. Name the approver for the production release gate.
3. Confirm who receives the daily alerts.

*Where to look: `docs/05_audit_pack.md`, `docs/01_dq_scorecard.md`, `docs/04_remediation_plan.md`.*
"""


def patient_care(f: dict) -> str:
    r = f["rule"]
    bf = f["backfill"]
    return f"""# Memo for Patient Care: what to trust in the clinical data

*As of {f["as_of"]}. Prepared for clinical leads. No patient names are used; records are referred to by id.*

## The answer in three lines

1. **{r["C03"]["rows"]} of {r["C03"]["of"]} medical records ({r["C03"]["pct"]:.1f}%) have no medication recorded.** The field holds the word "None". We cannot tell whether "no medication was needed" or "nobody entered it".
2. **Every administration record points at the wrong patient's prescription:** {r["A30"]["rows"]} of {r["A30"]["of"]}. Do not use the link between doses given and prescriptions to answer a safety question until it is fixed.
3. **We did not fill the gaps.** We tried matching the {int(bf.loc["C03", "records_failing_before"])} records to prescriptions on a copy of the data: {int(bf.loc["C03", "applied_to_copy"])} could be filled safely. {int(bf.loc["C03", "conflicts_with_plan"])} matches contradicted the treatment plan and were rejected. Guessing clinical data is worse than a gap.

## Other things to be aware of

- **{r["A31"]["rows"]} of {r["A31"]["of"]} dose records** show a different unit from the prescription. This is deferred until the prescription link is fixed, because we cannot compare against the right prescription yet.
- **{r["A24"]["rows"]} admissions** show a discharge before the admission, and **{r["A28"]["rows"]} prescriptions** end before they start.
- **{r["A16"]["rows"]} patient ids appear more than once** in the patient list.
- {r["C02"]["rows"]} visits are not linked to an appointment, so a visit cannot always be tied back to the booking.

## What we need from clinical leads

1. Tell us what "None" means in the medication field (no medication, or not recorded).
2. Review the {int(bf.loc["C03", "records_failing_before"])} records by hand. The list with a suggested match, where one exists, is in `outputs/gold/backfill_c03.csv`.
3. Tell us which dose records matter most for a safety review, so the link is fixed for those first.

*Where to look: `docs/04_remediation_plan.md`, `docs/02_root_cause_report.md`.*
"""


MEMOS = {
    "01_finance_memo.md": finance,
    "02_compliance_memo.md": compliance,
    "03_patient_care_memo.md": patient_care,
}
