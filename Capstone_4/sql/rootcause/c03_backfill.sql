-- C03: could the 40 'None' records be filled from Prescriptions (same patient, prescribed on or before the record date)?
SELECT
    count(*) AS none_records,
    count(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM Prescriptions AS p
WHERE i(p.patient_id) = i(m.patient_id)
    )) AS patient_has_any_prescription,
    count(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM Prescriptions AS p
        WHERE i(p.patient_id) = i(m.patient_id) AND d(p.start_date) <= d(m.record_date)
    )) AS prescribed_on_or_before_record,
    count(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM Prescriptions AS p
        WHERE i(p.patient_id) = i(m.patient_id) AND i(p.doctor_id) = i(m.doctor_id)
    )) AS same_patient_and_doctor
FROM Medical_Records AS m
WHERE lower(trim(m.prescribed_meds)) = 'none'
