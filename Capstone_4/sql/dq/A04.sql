-- A04 | Insurance_Claims: approved_date earlier than submitted_date
SELECT
    yr(t.submitted_date) AS yr,
    t._row_num AS row_num,
    coalesce(d(t.approved_date) < d(t.submitted_date), FALSE) AS failed,
    coalesce(d(t.approved_date) IS NOT NULL, FALSE) AS in_scope
FROM Insurance_Claims AS t
