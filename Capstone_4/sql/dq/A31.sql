-- A31 | Prescription_Administration: administered unit differs from prescribed unit
SELECT
    yr(t.administered_datetime) AS yr,
    t._row_num AS row_num,
    coalesce(t.dosage_unit <> r.dosage_unit, FALSE) AS failed,
    coalesce(r._row_num IS NOT NULL, FALSE) AS in_scope
FROM Prescription_Administration AS t LEFT JOIN Prescriptions AS r ON i(t.prescription_id) = i(r.prescription_id)
