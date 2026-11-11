-- A44 | Insurance_Claims: approved_amount larger than submitted_amount
SELECT
    yr(t.submitted_date) AS yr,
    t._row_num AS row_num,
    coalesce(n(t.approved_amount) > n(t.submitted_amount), FALSE) AS failed,
    coalesce(n(t.approved_amount) IS NOT NULL AND n(t.submitted_amount) IS NOT NULL, FALSE) AS in_scope
FROM Insurance_Claims AS t
