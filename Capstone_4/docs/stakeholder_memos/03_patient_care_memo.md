# Memo for Patient Care: what to trust in the clinical data

*As of 2026-10-21. Prepared for clinical leads. No patient names are used; records are referred to by id.*

## The answer in three lines

1. **40 of 206 medical records (19.4%) have no medication recorded.** The field holds the word "None". We cannot tell whether "no medication was needed" or "nobody entered it".
2. **Every administration record points at the wrong patient's prescription:** 400 of 400. Do not use the link between doses given and prescriptions to answer a safety question until it is fixed.
3. **We did not fill the gaps.** We tried matching the 40 records to prescriptions on a copy of the data: 0 could be filled safely. 2 matches contradicted the treatment plan and were rejected. Guessing clinical data is worse than a gap.

## Other things to be aware of

- **349 of 400 dose records** show a different unit from the prescription. This is deferred until the prescription link is fixed, because we cannot compare against the right prescription yet.
- **152 admissions** show a discharge before the admission, and **118 prescriptions** end before they start.
- **55 patient ids appear more than once** in the patient list.
- 123 visits are not linked to an appointment, so a visit cannot always be tied back to the booking.

## What we need from clinical leads

1. Tell us what "None" means in the medication field (no medication, or not recorded).
2. Review the 40 records by hand. The list with a suggested match, where one exists, is in `outputs/gold/backfill_c03.csv`.
3. Tell us which dose records matter most for a safety review, so the link is fixed for those first.

*Where to look: `docs/04_remediation_plan.md`, `docs/02_root_cause_report.md`.*
