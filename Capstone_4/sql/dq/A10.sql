-- A10 | Billing: amount_paid larger than patient_responsibility
SELECT
    yr(t.billing_date) AS yr,
    t._row_num AS row_num,
    coalesce(n(t.amount_paid) > n(t.patient_responsibility) + 0.01, FALSE) AS failed,
    coalesce(n(t.amount_paid) IS NOT NULL, FALSE) AS in_scope
FROM Billing AS t
