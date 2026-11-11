-- C01 | Insurance_Claims: approved_amount missing
SELECT
    yr(t.submitted_date) AS yr,
    t._row_num AS row_num,
    coalesce(missing(t.approved_amount), FALSE) AS failed,
    coalesce(TRUE, FALSE) AS in_scope
FROM Insurance_Claims AS t
