-- C03: which diagnosis chapters carry 'None' (clinical plausibility check)
SELECT
    icd10_chapter,
    count(*) AS records,
    count(*) FILTER (WHERE lower(trim(prescribed_meds)) = 'none') AS meds_none,
    round(100.0 * count(*) FILTER (WHERE lower(trim(prescribed_meds)) = 'none') / count(*), 1) AS pct_none
FROM Medical_Records
GROUP BY icd10_chapter
ORDER BY pct_none DESC
