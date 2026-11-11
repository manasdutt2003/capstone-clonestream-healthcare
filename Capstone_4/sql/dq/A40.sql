-- A40 | Nurse_Assignments: same nurse assigned twice on the same date
SELECT
    yr(t.shift_date) AS yr,
    t._row_num AS row_num,
    coalesce(t.rn > 1, FALSE) AS failed,
    coalesce(TRUE, FALSE) AS in_scope
FROM (
    SELECT
        *,
        row_number() OVER (PARTITION BY nurse_id, shift_date ORDER BY _row_num) AS rn
    FROM Nurse_Assignments
) AS t
