-- A25 | Appointments: updated_at earlier than created_at
SELECT
    yr(t.appointment_date) AS yr,
    t._row_num AS row_num,
    coalesce(ts(t.updated_at) < ts(t.created_at), FALSE) AS failed,
    coalesce(ts(t.updated_at) IS NOT NULL AND ts(t.created_at) IS NOT NULL, FALSE) AS in_scope
FROM Appointments AS t
