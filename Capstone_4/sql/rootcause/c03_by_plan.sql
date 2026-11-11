-- C03: is 'None' explained by the treatment plan? A plan that names a drug should have a prescribed medicine.
SELECT
    CASE
        WHEN treatment_plan IN (
            'Atorvastatin 20mg', 'Albuterol', 'Levothyroxine', 'Lisinopril 10mg', 'Metformin 500mg',
            'Ibuprofen 400mg', 'Sertraline 50mg', 'Amoxicillin 500mg', 'Omeprazole 20mg'
        ) THEN 'plan names a drug'
        ELSE 'plan is not a drug (diet, therapy, referral, test, vaccine)'
    END AS plan_type,
    count(*) AS records,
    count(*) FILTER (WHERE lower(trim(prescribed_meds)) = 'none') AS meds_none,
    round(100.0 * count(*) FILTER (WHERE lower(trim(prescribed_meds)) = 'none') / count(*), 1) AS pct_none
FROM Medical_Records
GROUP BY plan_type
ORDER BY plan_type
