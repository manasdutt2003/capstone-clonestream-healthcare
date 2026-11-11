-- A39 | Nurses: nurse supervises themselves
SELECT
    yr(t.hire_date) AS yr,
    t._row_num AS row_num,
    coalesce(i(t.supervisor_nurse_id) = i(t.nurse_id), FALSE) AS failed,
    coalesce(t.supervisor_nurse_id IS NOT NULL, FALSE) AS in_scope
FROM Nurses AS t
