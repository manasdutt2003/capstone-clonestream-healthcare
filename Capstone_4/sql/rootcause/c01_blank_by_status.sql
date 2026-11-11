-- C01: is a blank approved_amount linked to the claim's status?
SELECT
    claim_status,
    count(*) AS claims,
    count(*) FILTER (WHERE missing(approved_amount)) AS approved_amount_blank,
    count(*) FILTER (WHERE missing(approved_date)) AS approved_date_blank,
    count(*) FILTER (WHERE NOT missing(paid_date)) AS paid_date_present
FROM Insurance_Claims
GROUP BY claim_status
ORDER BY claims DESC
