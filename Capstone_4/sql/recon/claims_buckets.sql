-- One row per claim: which reconciliation bucket does it belong to, and what is held back?
-- Money-affecting problems put a claim in the DQ Hold bucket. Date-only problems are flagged but do not move the money (DECISIONS D-021).
WITH base AS (
    SELECT
        i(claim_id) AS claim_id,
        i(patient_id) AS patient_id,
        claim_number,
        claim_status,
        n(submitted_amount) AS submitted_amount,
        n(approved_amount) AS approved_amount,
        d(submitted_date) AS submitted_date,
        d(approved_date) AS approved_date,
        d(paid_date) AS paid_date,
        _row_num
    FROM Insurance_Claims
),

held AS (
    SELECT
        *,
        CASE
            WHEN claim_status NOT IN ('Approved', 'Denied', 'Appealed', 'Submitted', 'Pending', 'In Review') OR claim_status IS NULL
                THEN 'Unrecognised claim status'
            WHEN submitted_amount IS NULL THEN 'Submitted amount missing'
            WHEN submitted_amount < 0 THEN 'Negative submitted amount'
            WHEN approved_amount > submitted_amount THEN 'Approved amount above submitted amount'
            WHEN claim_status = 'Approved' AND paid_date > as_of() THEN 'Paid date is after the as-of date'
        END AS hold_reason
    FROM base
)

SELECT
    claim_id,
    patient_id,
    claim_number,
    claim_status,
    submitted_amount,
    approved_amount,
    submitted_date,
    approved_date,
    paid_date,
    hold_reason,
    CASE
        WHEN hold_reason IS NOT NULL THEN 'DQ Hold'
        WHEN claim_status = 'Approved' AND paid_date IS NOT NULL THEN 'Paid'
        WHEN claim_status = 'Approved' THEN 'Approved, not yet paid'
        WHEN claim_status = 'Denied' THEN 'Denied'
        WHEN claim_status = 'Appealed' THEN 'Under appeal'
        ELSE 'Pipeline'
    END AS bucket,
    concat_ws(
        '; ',
        CASE WHEN submitted_date > as_of() THEN 'Submitted date in the future' END,
        CASE WHEN approved_date > as_of() THEN 'Approved date in the future' END,
        CASE WHEN approved_date < submitted_date THEN 'Approved before submitted' END,
        CASE WHEN paid_date < approved_date THEN 'Paid before approved' END
    ) AS date_flags,
    CASE
        WHEN submitted_date IS NULL OR submitted_date > as_of() THEN NULL
        ELSE date_diff('day', submitted_date, as_of())
    END AS age_days,
    _row_num AS source_row
FROM held
ORDER BY claim_id
