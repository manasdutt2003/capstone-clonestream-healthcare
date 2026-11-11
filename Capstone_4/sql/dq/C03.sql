-- C03 | Medical_Records: prescribed_meds missing (stored as the text "None")
SELECT
    yr(t.record_date) AS yr,
    t._row_num AS row_num,
    coalesce((t.prescribed_meds IS NULL OR lower(trim(t.prescribed_meds)) IN ('none', 'n/a', 'null', 'unknown', '')), FALSE) AS failed,
    coalesce(TRUE, FALSE) AS in_scope
FROM Medical_Records AS t
