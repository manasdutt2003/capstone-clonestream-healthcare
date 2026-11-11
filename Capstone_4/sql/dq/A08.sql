-- A08 | Insurance_Claims: Denied claim without a denial_reason
SELECT
    yr(t.submitted_date) AS yr,
    t._row_num AS row_num,
    coalesce(missing(t.denial_reason), FALSE) AS failed,
    coalesce(t.claim_status = 'Denied', FALSE) AS in_scope
FROM Insurance_Claims AS t
