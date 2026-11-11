-- A11 | Billing: negative total_amount
SELECT
    yr(t.billing_date) AS yr,
    t._row_num AS row_num,
    coalesce(n(t.total_amount) < 0, FALSE) AS failed,
    coalesce(n(t.total_amount) IS NOT NULL, FALSE) AS in_scope
FROM Billing AS t
