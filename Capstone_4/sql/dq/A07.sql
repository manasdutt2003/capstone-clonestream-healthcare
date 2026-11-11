-- A07 | Insurance_Claims: negative submitted_amount
SELECT
    yr(t.submitted_date) AS yr,
    t._row_num AS row_num,
    coalesce(n(t.submitted_amount) < 0, FALSE) AS failed,
    coalesce(n(t.submitted_amount) IS NOT NULL, FALSE) AS in_scope
FROM Insurance_Claims AS t
