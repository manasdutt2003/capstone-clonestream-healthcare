# Data Cleaning Report

*Generated from `outputs/gold/change_log.csv`. 3,156 cells changed across 8 tables. No rows were added or removed.*

## Principles

1. **Never drop a row.** Row counts before and after are identical (table below).
2. **Fix format, not facts.** Dates, phone numbers, spelling variants and placeholder text are standardised.
3. **Null what is impossible, never invent.** A height of -10 cm, a birth date in the future or `not-an-email` becomes blank. The only computed value is BMI, which is a formula of height and weight.
4. **Do not touch money, doses or foreign keys.** They are flagged by the DQ engine because changing them would hide the evidence auditors need.
5. **Every change is logged** (table, Excel row, column, old value, new value, rule) in `change_log.csv`.

## Date rules

| Input | Becomes | Rule |
|---|---|---|
| `2024-03-12T09:00:00` in a date column | `2024-03-12` | `date_trimmed_time` |
| `01/15/1987`, `01-01-2020` | `1987-01-15`, `2020-01-01` | `date_reformatted` (US month-first; a first number above 12 is treated as the day) |
| `not available`, `tomorrow` | blank | `date_unparseable` |
| `2025-13-01` (month 13) | blank | `date_invalid` (cannot tell whether day and month were swapped) |
| `1800-01-01`, `1900-01-01`, `2099-01-01` | blank | `date_sentinel` (placeholder for 'no date') |
| Date of birth after the as-of date | blank | `dob_in_future` |

## Changes by rule

| rule | cells_changed |
|---|---|
| category_standardised | 734 |
| placeholder_to_null | 426 |
| number_out_of_range | 326 |
| phone_invalid | 228 |
| category_unmapped | 205 |
| bmi_recomputed | 181 |
| whitespace_trimmed | 149 |
| number_non_numeric | 136 |
| email_invalid | 128 |
| date_sentinel | 125 |
| date_unparseable | 101 |
| date_reformatted | 99 |
| group_placeholder | 96 |
| phone_reformatted | 62 |
| policy_placeholder | 59 |
| dob_in_future | 50 |
| date_invalid | 48 |
| id_holds_date | 2 |
| icd10_invalid | 1 |


## Changes by table and column

| table | column | rule | cells_changed |
|---|---|---|---|
| Appointments | appointment_date | date_sentinel | 3 |
| Doctors | consultation_fee | number_out_of_range | 6 |
| Doctors | rating | number_out_of_range | 5 |
| Doctors | years_exp | number_out_of_range | 7 |
| Hospitals | city | category_standardised | 7 |
| Medical_Records | diagnosis_code | icd10_invalid | 1 |
| Medical_Records | prescribed_meds | placeholder_to_null | 40 |
| Patients | alcohol_consumption | category_standardised | 130 |
| Patients | allergy_info | placeholder_to_null | 64 |
| Patients | blood_type | category_standardised | 63 |
| Patients | blood_type | category_unmapped | 71 |
| Patients | bmi | bmi_recomputed | 181 |
| Patients | bmi | number_non_numeric | 47 |
| Patients | bmi | number_out_of_range | 100 |
| Patients | chronic_conditions | placeholder_to_null | 58 |
| Patients | chronic_conditions | whitespace_trimmed | 21 |
| Patients | current_medications | placeholder_to_null | 69 |
| Patients | date_of_birth | date_reformatted | 48 |
| Patients | date_of_birth | date_sentinel | 58 |
| Patients | date_of_birth | date_unparseable | 46 |
| Patients | date_of_birth | dob_in_future | 50 |
| Patients | email | email_invalid | 128 |
| Patients | emergency_contact_name | placeholder_to_null | 73 |
| Patients | emergency_contact_phone | phone_invalid | 137 |
| Patients | employer_name | placeholder_to_null | 67 |
| Patients | ethnicity | category_standardised | 64 |
| Patients | ethnicity | category_unmapped | 64 |
| Patients | gender | category_standardised | 133 |
| Patients | height_cm | number_non_numeric | 47 |
| Patients | height_cm | number_out_of_range | 103 |
| Patients | insurance_group_number | group_placeholder | 96 |
| Patients | insurance_policy_number | policy_placeholder | 59 |
| Patients | language_preference | category_standardised | 75 |
| Patients | language_preference | category_unmapped | 70 |
| Patients | last_name | placeholder_to_null | 55 |
| Patients | last_visit_date | date_invalid | 1 |
| Patients | last_visit_date | date_reformatted | 1 |
| Patients | last_visit_date | date_sentinel | 58 |
| Patients | last_visit_date | date_unparseable | 1 |
| Patients | marital_status | category_standardised | 59 |
| Patients | marital_status | whitespace_trimmed | 65 |
| Patients | patient_status | category_standardised | 70 |
| Patients | patient_status | whitespace_trimmed | 63 |
| Patients | phone_number | phone_invalid | 91 |
| Patients | phone_number | phone_reformatted | 62 |
| Patients | registration_date | date_invalid | 47 |
| Patients | registration_date | date_reformatted | 50 |
| Patients | registration_date | date_unparseable | 54 |
| Patients | smoking_status | category_standardised | 133 |
| Patients | weight_kg | number_non_numeric | 42 |
| Patients | weight_kg | number_out_of_range | 104 |
| Prescriptions | start_date | date_sentinel | 6 |
| Referrals | patient_id | id_holds_date | 2 |
| Visits | oxygen_saturation | number_out_of_range | 1 |


## Row counts (nothing dropped)

| Table | Raw rows | Clean rows |
|---|---:|---:|
| Admissions | 350 | 350 |
| Appointments | 250 | 250 |
| Billing | 250 | 250 |
| Departments | 21 | 21 |
| Doctors | 620 | 620 |
| Hierarchy | 641 | 641 |
| Hospitals | 25 | 25 |
| Insurance_Claims | 250 | 250 |
| Medical_Records | 206 | 206 |
| Nurse_Assignments | 350 | 350 |
| Nurses | 120 | 120 |
| Patient_Insurance | 300 | 300 |
| Patient_Procedures | 250 | 250 |
| Patients | 5,005 | 5,005 |
| Prescription_Administration | 400 | 400 |
| Prescriptions | 500 | 500 |
| Procedure_Codes | 45 | 45 |
| Referential_Integrity | 20 | 20 |
| Referrals | 200 | 200 |
| Visits | 400 | 400 |

## Deliberately not changed (flagged instead)

- Orphan and sentinel foreign keys (for example patient ids 0, -1, 88888, 99991). Rules `R-*`.
- Duplicate patient ids and e-mails (A16, A17). Merging people needs a business decision.
- Money fields: negative or inconsistent claim and bill amounts (A07, A09, A10, A11, A44).
- Drug doses and clinical vitals outside typical ranges (rules `X-*`). They may be genuine.
- Date-order violations (A04, A05, A24, A25, A28, A32, A37). The correct order is unknown.
- Future-dated events (rules `T-*`). We flag, we do not guess the true date.
- Repeated 'default' dates such as 2020-01-01 or 2025-01-01 (rules `P-*`).

## Judgement calls

- **`None` means different things.** In `Medical_Records.prescribed_meds` the text `None` is treated as *missing* (this is the brief's 40-record defect). In allergy, surgery, family-history, alcohol, complications and accreditation columns `None` is a valid answer and is kept as `None`.
- **Ambiguous values are blanked, not guessed:** blood type `AB` (no Rh sign), ethnicity `Human`, language `Spanglish`.
- **Mapped with a stated assumption:** `2 beers/week` and `Sometimes` -> `Occasional`; `Smoker` -> `Current Smoker`; `caucasian` -> `White`; hospital city abbreviations (Philly, Jax, Indy, SF, OKC, DC, Vegas) -> full names.
- **Placeholders:** the group number `G1234` (96 rows) and policy `POL-ABC` (59) are constants, not real identifiers, so they are blanked.
