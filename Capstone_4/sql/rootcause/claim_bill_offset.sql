-- Hypothesis "positional shift": if bills were attached k rows off, some k would make the patients match.
SELECT
    r.k AS offset_k,
    count(b.billing_id) AS pairs,
    count(*) FILTER (WHERE i(b.patient_id) = i(c.patient_id)) AS same_patient
FROM Insurance_Claims AS c
CROSS JOIN range(-10, 11) AS r (k)
LEFT JOIN Billing AS b ON i(b.billing_id) = i(c.billing_id) + r.k
GROUP BY r.k
ORDER BY r.k
