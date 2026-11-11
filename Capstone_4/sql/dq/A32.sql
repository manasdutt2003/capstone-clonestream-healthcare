-- A32 | Prescription_Administration: given before the prescription start_date
SELECT
    yr(t.administered_datetime) AS yr,
    t._row_num AS row_num,
    coalesce(d(t.administered_datetime) < d(r.start_date), FALSE) AS failed,
    coalesce(r._row_num IS NOT NULL AND d(r.start_date) IS NOT NULL, FALSE) AS in_scope
FROM Prescription_Administration AS t LEFT JOIN Prescriptions AS r ON i(t.prescription_id) = i(r.prescription_id)
