-- Ten example claim / bill pairs for the auditors (first ten by claim id)
SELECT
    c.claim_id,
    c.billing_id,
    c.patient_id AS claim_patient_id,
    b.patient_id AS bill_patient_id,
    c.submitted_amount,
    b.total_amount AS bill_total,
    c.submitted_date,
    b.billing_date
FROM Insurance_Claims AS c INNER JOIN Billing AS b ON i(c.billing_id) = i(b.billing_id)
ORDER BY i(c.claim_id)
LIMIT 10
