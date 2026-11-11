# Memo for Compliance: what the auditors will see

*As of 2026-10-21. Prepared for the Compliance lead ahead of Friday's audit.*

## The answer in three lines

1. **We ran 441 checks across all 19 tables and found problems in 164.** 28 are serious (5 critical, 23 high), spread over 11 tables.
2. **This is not a recent incident.** The share of bad records is about the same in every year from 2020 (no statistical evidence of a change). The system never stopped bad data going in.
3. **Nothing was deleted or invented.** The cleaned dataset has every original row. Money, doses and links are flagged, never changed, so the evidence is intact.

## The points auditors will ask about

| Question | What the data shows |
|---|---|
| Are visits linked to appointments? | **123 of 400 visits** (30.8%) have no appointment. |
| Do patient ids always exist? | **116 records in 8 tables** carry placeholder ids (0, -1, 88888, 9999x). They start upstream, in the appointment system. |
| Were bills raised for visits that did not happen? | **81 bills** are for cancelled or no-show appointments. This needs a compliance review: it may be a billing error. |
| Can dates be trusted? | 84 of 97 paid claims have dates out of order. |
| Is there an audit trail? | Yes. Every pipeline run is logged with who, when, the code version, and a fingerprint of each output (`outputs/gold/audit_log.csv`). |

## What is being done

- **Fix at the source** (owners named in `docs/04_remediation_plan.md`). Repairing history is not possible: a simulated backfill recovered 0 of 123 unlinked visits.
- **Stop it recurring:** 49 checks would run when data is loaded. On this data they would have rejected 1,903 records. They start in warn-only mode.
- **Watch it daily:** a daily job raises an alert when a critical check fails on more than 5% of records. Today it raises 5.

## What we need from Compliance

1. Review the 81 bills for cancelled or no-show appointments.
2. Name the approver for the production release gate.
3. Confirm who receives the daily alerts.

*Where to look: `docs/05_audit_pack.md`, `docs/01_dq_scorecard.md`, `docs/04_remediation_plan.md`.*
