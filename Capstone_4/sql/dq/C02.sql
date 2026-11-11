-- C02 | Visits: appointment_id missing (visit not linked to an appointment)
SELECT
    yr(t.visit_date) AS yr,
    t._row_num AS row_num,
    coalesce(t.appointment_id IS NULL, FALSE) AS failed,
    coalesce(TRUE, FALSE) AS in_scope
FROM Visits AS t
