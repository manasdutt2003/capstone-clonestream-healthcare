-- A09 | Billing: insurance_covered + patient_responsibility does not equal total_amount
SELECT
    yr(t.billing_date) AS yr,
    t._row_num AS row_num,
    coalesce(abs(n(t.insurance_covered) + n(t.patient_responsibility) - n(t.total_amount)) > 0.01, FALSE) AS failed,
    coalesce(n(t.insurance_covered) IS NOT NULL AND n(t.patient_responsibility) IS NOT NULL AND n(t.total_amount) IS NOT NULL, FALSE) AS in_scope
FROM Billing AS t
