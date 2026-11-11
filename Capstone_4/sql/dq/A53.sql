-- A53 | Patients: last_visit_date earlier than registration_date
SELECT
    yr(t.registration_date) AS yr,
    t._row_num AS row_num,
    coalesce(d(t.last_visit_date) < d(t.registration_date), FALSE) AS failed,
    coalesce(d(t.last_visit_date) IS NOT NULL AND d(t.registration_date) IS NOT NULL, FALSE) AS in_scope
FROM Patients AS t
