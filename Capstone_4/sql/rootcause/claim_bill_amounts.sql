-- How far apart are a claim's submitted amount and the bill it points at?
SELECT
    count(*) AS pairs,
    round(median(n(c.submitted_amount) / nullif(n(b.total_amount), 0)), 1) AS median_ratio,
    round(quantile_cont(n(c.submitted_amount) / nullif(n(b.total_amount), 0), 0.1), 1) AS p10_ratio,
    round(quantile_cont(n(c.submitted_amount) / nullif(n(b.total_amount), 0), 0.9), 1) AS p90_ratio,
    count(*) FILTER (WHERE n(c.submitted_amount) > n(b.total_amount)) AS claim_above_bill,
    count(*) FILTER (WHERE n(c.submitted_amount) BETWEEN 0.8 * n(b.total_amount) AND 1.25 * n(b.total_amount)) AS within_25_percent
FROM Insurance_Claims AS c INNER JOIN Billing AS b ON i(c.billing_id) = i(b.billing_id)
