-- A38 | Patient_Insurance: linked claim belongs to a different patient
SELECT
    yr(t.coverage_start) AS yr,
    t._row_num AS row_num,
    coalesce(i(t.patient_id) <> i(c.patient_id), FALSE) AS failed,
    coalesce(c._row_num IS NOT NULL, FALSE) AS in_scope
FROM Patient_Insurance AS t LEFT JOIN Insurance_Claims AS c ON i(t.claim_id) = i(c.claim_id)
