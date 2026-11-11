-- A01 | Insurance_Claims: billing_id reused by more than one claim
SELECT
    yr(t.submitted_date) AS yr,
    t._row_num AS row_num,
    coalesce(t.rn > 1, FALSE) AS failed,
    coalesce(NOT missing(t.billing_id), FALSE) AS in_scope
FROM (
    SELECT
        *,
        row_number() OVER (PARTITION BY billing_id ORDER BY _row_num) AS rn
    FROM Insurance_Claims
) AS t
