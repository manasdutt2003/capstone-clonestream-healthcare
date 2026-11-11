-- A30 | Prescription_Administration: administration patient differs from the prescription patient
SELECT
    yr(t.administered_datetime) AS yr,
    t._row_num AS row_num,
    coalesce(i(t.patient_id) <> i(r.patient_id), FALSE) AS failed,
    coalesce(r._row_num IS NOT NULL, FALSE) AS in_scope
FROM Prescription_Administration AS t LEFT JOIN Prescriptions AS r ON i(t.prescription_id) = i(r.prescription_id)
