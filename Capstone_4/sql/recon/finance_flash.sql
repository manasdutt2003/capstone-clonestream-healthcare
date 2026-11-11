-- Finance Flash: where does each claim dollar sit today? (as recorded, before DQ holds are separated in Sprint 3)
SELECT
    claim_status,
    count(*) AS claims,
    round(sum(n(submitted_amount)), 2) AS submitted,
    round(sum(n(approved_amount)), 2) AS approved,
    count(*) FILTER (WHERE NOT missing(paid_date)) AS claims_with_paid_date,
    count(*) FILTER (WHERE missing(approved_amount)) AS approved_amount_blank,
    count(*) FILTER (WHERE n(submitted_amount) < 0 OR n(approved_amount) > n(submitted_amount)) AS amount_anomalies
FROM Insurance_Claims
GROUP BY claim_status
ORDER BY submitted DESC
