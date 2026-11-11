-- A34 | Referrals: doctor referred to themselves
SELECT
    yr(t.referral_date) AS yr,
    t._row_num AS row_num,
    coalesce(i(t.referring_doctor_id) = i(t.referred_doctor_id), FALSE) AS failed,
    coalesce(TRUE, FALSE) AS in_scope
FROM Referrals AS t
