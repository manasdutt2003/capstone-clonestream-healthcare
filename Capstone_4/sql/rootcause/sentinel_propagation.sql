-- Does a placeholder patient id on a bill come from the appointment it belongs to?
-- (Billing -> Appointments links are sound, so this shows where the placeholder first appeared.)
WITH bills AS (
    SELECT
        b.patient_id AS bill_patient,
        a.patient_id AS appointment_patient,
        NOT EXISTS (
            SELECT 1
            FROM Patients AS p
            WHERE i(p.patient_id) = i(b.patient_id)
        ) AS orphan
    FROM Billing AS b
    INNER JOIN Appointments AS a ON i(b.appointment_id) = i(a.appointment_id)
)

SELECT
    count(*) FILTER (WHERE orphan) AS bills_with_orphan_patient,
    count(*) FILTER (WHERE orphan AND i(appointment_patient) = i(bill_patient)) AS appointment_has_same_orphan_id
FROM bills
