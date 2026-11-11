-- A03 | Insurance_Claims: submitted_amount larger than the linked bill total
SELECT
    yr(t.submitted_date) AS yr,
    t._row_num AS row_num,
    coalesce(n(t.submitted_amount) > n(b.total_amount), FALSE) AS failed,
    coalesce(b._row_num IS NOT NULL, FALSE) AS in_scope
FROM Insurance_Claims AS t LEFT JOIN Billing AS b ON i(t.billing_id) = i(b.billing_id)
