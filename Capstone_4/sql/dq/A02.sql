-- A02 | Insurance_Claims: claim patient differs from the patient on the linked bill
SELECT
    yr(t.submitted_date) AS yr,
    t._row_num AS row_num,
    coalesce(i(t.patient_id) <> i(b.patient_id), FALSE) AS failed,
    coalesce(b._row_num IS NOT NULL, FALSE) AS in_scope
FROM Insurance_Claims AS t LEFT JOIN Billing AS b ON i(t.billing_id) = i(b.billing_id)
