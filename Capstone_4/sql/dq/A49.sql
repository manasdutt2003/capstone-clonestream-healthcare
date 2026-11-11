-- A49 | Patients: bmi inconsistent with height and weight
SELECT
    yr(t.registration_date) AS yr,
    t._row_num AS row_num,
    coalesce(abs(n(t.bmi) - n(t.weight_kg) / pow(n(t.height_cm) / 100, 2)) > 2, FALSE) AS failed,
    coalesce(n(t.height_cm) BETWEEN 50 AND 250 AND n(t.weight_kg) BETWEEN 2 AND 300 AND n(t.bmi) BETWEEN 10 AND 80, FALSE) AS in_scope
FROM Patients AS t
