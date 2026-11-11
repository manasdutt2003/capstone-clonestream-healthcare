-- A12 | Billing: bill raised for a Cancelled or No-Show appointment
SELECT
    yr(t.billing_date) AS yr,
    t._row_num AS row_num,
    coalesce(a.status IN ('Cancelled', 'No-Show'), FALSE) AS failed,
    coalesce(a._row_num IS NOT NULL, FALSE) AS in_scope
FROM Billing AS t LEFT JOIN Appointments AS a ON i(t.appointment_id) = i(a.appointment_id)
