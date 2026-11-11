-- A29 | Prescriptions: marked active although end_date has passed
SELECT
    yr(t.start_date) AS yr,
    t._row_num AS row_num,
    coalesce(d(t.end_date) < as_of(), FALSE) AS failed,
    coalesce(t.is_active = 'True' AND d(t.end_date) IS NOT NULL, FALSE) AS in_scope
FROM Prescriptions AS t
