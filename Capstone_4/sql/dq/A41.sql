-- A41 | Visits: systolic_bp not greater than diastolic_bp
SELECT
    yr(t.visit_date) AS yr,
    t._row_num AS row_num,
    coalesce(i(t.systolic_bp) <= i(t.diastolic_bp), FALSE) AS failed,
    coalesce(i(t.systolic_bp) IS NOT NULL AND i(t.diastolic_bp) IS NOT NULL, FALSE) AS in_scope
FROM Visits AS t
