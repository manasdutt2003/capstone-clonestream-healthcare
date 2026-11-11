-- C02: what do visits without an appointment have in common?
WITH v AS (
    SELECT
        coalesce(notes, '(blank)') AS visit_note,
        appointment_id IS NULL AS no_appt,
        (
            SELECT count(*)
            FROM Appointments AS a
            WHERE i(a.patient_id) = i(vis.patient_id)
        ) > 0 AS patient_has_appts
    FROM Visits AS vis
)

SELECT
    visit_note,
    count(*) AS visits,
    count(*) FILTER (WHERE no_appt) AS missing_appointment,
    round(100.0 * count(*) FILTER (WHERE no_appt) / count(*), 1) AS pct_missing,
    count(*) FILTER (WHERE no_appt AND patient_has_appts) AS missing_but_patient_has_appointments
FROM v
GROUP BY visit_note
ORDER BY visits DESC
