-- Orphan patient ids by table, grouped by the kind of placeholder they look like
WITH orphans AS (
    SELECT
        'Appointments' AS tbl,
        patient_id AS pid
    FROM Appointments
    UNION ALL
    SELECT
        'Visits' AS tbl,
        patient_id AS pid
    FROM Visits
    UNION ALL
    SELECT
        'Medical_Records' AS tbl,
        patient_id AS pid
    FROM Medical_Records
    UNION ALL
    SELECT
        'Billing' AS tbl,
        patient_id AS pid
    FROM Billing
    UNION ALL
    SELECT
        'Prescriptions' AS tbl,
        patient_id AS pid
    FROM Prescriptions
    UNION ALL
    SELECT
        'Admissions' AS tbl,
        patient_id AS pid
    FROM Admissions
    UNION ALL
    SELECT
        'Prescription_Administration' AS tbl,
        patient_id AS pid
    FROM Prescription_Administration
    UNION ALL
    SELECT
        'Referrals' AS tbl,
        patient_id AS pid
    FROM Referrals
)

SELECT
    o.tbl AS table_name,
    CASE
        WHEN i(o.pid) IS NULL THEN 'not a number'
        WHEN i(o.pid) <= 0 THEN 'zero or negative'
        WHEN i(o.pid) = 88888 THEN '88888'
        WHEN i(o.pid) BETWEEN 99990 AND 99999 THEN '9999x'
        ELSE 'other'
    END AS placeholder_kind,
    count(*) AS rows_affected,
    count(DISTINCT o.pid) AS distinct_values
FROM orphans AS o
WHERE
    o.pid IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM Patients AS p
        WHERE i(p.patient_id) = i(o.pid)
    )
GROUP BY o.tbl, placeholder_kind
ORDER BY o.tbl ASC, rows_affected DESC
