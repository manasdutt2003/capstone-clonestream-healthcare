-- A43b | Departments: duplicate phone extension
SELECT
    CAST(NULL AS VARCHAR) AS yr,
    t._row_num AS row_num,
    coalesce(t.rn > 1, FALSE) AS failed,
    coalesce(TRUE, FALSE) AS in_scope
FROM (
    SELECT
        *,
        row_number() OVER (PARTITION BY phone_extension ORDER BY _row_num) AS rn
    FROM Departments
) AS t
