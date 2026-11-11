-- A13 | Billing: billing_date after due_date
SELECT
    yr(t.billing_date) AS yr,
    t._row_num AS row_num,
    coalesce(d(t.billing_date) > d(t.due_date), FALSE) AS failed,
    coalesce(d(t.billing_date) IS NOT NULL AND d(t.due_date) IS NOT NULL, FALSE) AS in_scope
FROM Billing AS t
