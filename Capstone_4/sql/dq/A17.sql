-- A17 | Patients: duplicate e-mail address (valid e-mails only)
SELECT
    yr(t.registration_date) AS yr,
    t._row_num AS row_num,
    coalesce(t.rn > 1, FALSE) AS failed,
    coalesce(regexp_matches(t.email, '^[^@ ]+@[^@ .][^@ ]*[.][A-Za-z]{2,}$'), FALSE) AS in_scope
FROM (
    SELECT
        *,
        row_number() OVER (PARTITION BY lower(trim(email)) ORDER BY _row_num) AS rn
    FROM Patients
    WHERE regexp_matches(email, '^[^@ ]+@[^@ .][^@ ]*[.][A-Za-z]{2,}$')
) AS t
