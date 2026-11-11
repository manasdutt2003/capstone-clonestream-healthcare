-- A24 | Admissions: discharge_date earlier than admit_date
SELECT
    yr(t.admit_date) AS yr,
    t._row_num AS row_num,
    coalesce(d(t.discharge_date) < d(t.admit_date), FALSE) AS failed,
    coalesce(d(t.discharge_date) IS NOT NULL AND d(t.admit_date) IS NOT NULL, FALSE) AS in_scope
FROM Admissions AS t
