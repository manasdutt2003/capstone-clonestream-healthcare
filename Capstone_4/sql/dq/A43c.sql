-- A43c | Doctors: duplicate licence number
SELECT
    CAST(NULL AS VARCHAR) AS yr,
    t._row_num AS row_num,
    coalesce(t.rn > 1, FALSE) AS failed,
    coalesce(t.license_number IS NOT NULL, FALSE) AS in_scope
FROM (
    SELECT
        *,
        row_number() OVER (PARTITION BY license_number ORDER BY _row_num) AS rn
    FROM Doctors
) AS t
