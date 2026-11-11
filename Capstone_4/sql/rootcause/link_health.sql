-- Do child rows that DO have a link point at a parent row for the same patient?
-- Every link that carries a patient_id on both sides can be tested this way.
SELECT
    'Visits -> Appointments' AS link,
    count(*) AS linked_rows,
    count(*) FILTER (WHERE i(c.patient_id) = i(p.patient_id)) AS same_patient,
    median(abs(date_diff('day', d(c.visit_date), d(p.appointment_date)))) AS median_gap_days
FROM Visits AS c INNER JOIN Appointments AS p ON i(c.appointment_id) = i(p.appointment_id)
UNION ALL
SELECT
    'Medical_Records -> Appointments' AS link,
    count(*) AS linked_rows,
    count(*) FILTER (WHERE i(c.patient_id) = i(p.patient_id)) AS same_patient,
    median(abs(date_diff('day', d(c.record_date), d(p.appointment_date)))) AS median_gap_days
FROM Medical_Records AS c INNER JOIN Appointments AS p ON i(c.appointment_id) = i(p.appointment_id)
UNION ALL
SELECT
    'Billing -> Appointments' AS link,
    count(*) AS linked_rows,
    count(*) FILTER (WHERE i(c.patient_id) = i(p.patient_id)) AS same_patient,
    median(abs(date_diff('day', d(c.billing_date), d(p.appointment_date)))) AS median_gap_days
FROM Billing AS c INNER JOIN Appointments AS p ON i(c.appointment_id) = i(p.appointment_id)
UNION ALL
SELECT
    'Insurance_Claims -> Billing' AS link,
    count(*) AS linked_rows,
    count(*) FILTER (WHERE i(c.patient_id) = i(p.patient_id)) AS same_patient,
    median(abs(date_diff('day', d(c.submitted_date), d(p.billing_date)))) AS median_gap_days
FROM Insurance_Claims AS c INNER JOIN Billing AS p ON i(c.billing_id) = i(p.billing_id)
UNION ALL
SELECT
    'Patient_Insurance -> Insurance_Claims' AS link,
    count(*) AS linked_rows,
    count(*) FILTER (WHERE i(c.patient_id) = i(p.patient_id)) AS same_patient,
    CAST(NULL AS DOUBLE) AS median_gap_days
FROM Patient_Insurance AS c INNER JOIN Insurance_Claims AS p ON i(c.claim_id) = i(p.claim_id)
UNION ALL
SELECT
    'Prescription_Administration -> Prescriptions' AS link,
    count(*) AS linked_rows,
    count(*) FILTER (WHERE i(c.patient_id) = i(p.patient_id)) AS same_patient,
    median(abs(date_diff('day', d(c.administered_datetime), d(p.start_date)))) AS median_gap_days
FROM Prescription_Administration AS c INNER JOIN Prescriptions AS p ON i(c.prescription_id) = i(p.prescription_id)
