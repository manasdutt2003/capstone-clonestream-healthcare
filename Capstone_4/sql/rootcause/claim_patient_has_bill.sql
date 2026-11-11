-- Hypothesis "join on patient instead": do the claims' patients even appear in Billing?
SELECT
    count(*) AS claims,
    count(*) FILTER (WHERE EXISTS (SELECT 1 FROM Billing AS b
WHERE i(b.patient_id) = i(c.patient_id))) AS claims_whose_patient_has_a_bill
FROM Insurance_Claims AS c
