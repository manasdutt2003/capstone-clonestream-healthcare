-- A16 | Patients: duplicate patient_id
SELECT
    yr(t.registration_date) AS yr,
    t._row_num AS row_num,
    coalesce(t.rn > 1, FALSE) AS failed,
    coalesce(NOT missing(t.patient_id), FALSE) AS in_scope
FROM (
    SELECT
        *,
        row_number() OVER (PARTITION BY patient_id ORDER BY _row_num) AS rn
    FROM Patients
) AS t
