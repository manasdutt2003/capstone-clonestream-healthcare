-- A37 | Patient_Insurance: coverage_end earlier than coverage_start
SELECT
    yr(t.coverage_start) AS yr,
    t._row_num AS row_num,
    coalesce(d(t.coverage_end) < d(t.coverage_start), FALSE) AS failed,
    coalesce(TRUE, FALSE) AS in_scope
FROM Patient_Insurance AS t
