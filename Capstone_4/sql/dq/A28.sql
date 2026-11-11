-- A28 | Prescriptions: end_date earlier than start_date
SELECT
    yr(t.start_date) AS yr,
    t._row_num AS row_num,
    coalesce(d(t.end_date) < d(t.start_date), FALSE) AS failed,
    coalesce(d(t.end_date) IS NOT NULL AND d(t.start_date) IS NOT NULL, FALSE) AS in_scope
FROM Prescriptions AS t
