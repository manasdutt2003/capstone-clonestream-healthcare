# SPEC — CloneStream Healthcare Data Crisis (Capstone 3)

| | |
|---|---|
| **Owner** | Manas Dutt |
| **Programme** | Perficient Global AI First Academy — GGTP_BLR_DP_SEP_26, Week 4, Capstone 3 (individual) |
| **Inputs** | `Resources/HCLS.html` (executive brief + rubric), `Resources/HCLS.xlsx` (20 sheets) |
| **Spec version** | 1.5 — 2026-10-22 (Sprint 5 implemented: audit log with output hashes, PII-free Power BI tables, DAX and build guide, memos, audit pack) |
| **Companion docs** | `PLAN.md` (sprints, branches, git), `README.md` (living status), `DECISIONS.md` (decision log) |

This is the single source of truth for **what** gets built. `PLAN.md` says **when and in what order**. If they disagree, this file wins and `PLAN.md` is updated.

---

## 1. Problem statement

CloneStream Healthcare Network has data-integrity failures across claims, visits and medical records. Three stakeholders need answers on hard deadlines:

| Stakeholder | Need | Deadline | Priority |
|---|---|---|---|
| Finance (CFO) | A defensible claims-submitted vs claims-paid number, with confidence levels | **Wednesday 5 PM** | P0 |
| Compliance & Legal | Audit-ready evidence: scope, root cause, remediation, prevention; answer the "are we overcharging?" question | **Friday (auditors on-site)** | P0 |
| Patient Care | Know which patients have incomplete medication histories / follow-ups | Ongoing | P1 |

The brief asks for a 5-phase POC: scope → root cause → finance reconciliation → remediation plan → audit pack, all in Git, tested, and validated through CI/CD, with scheduled jobs and a Power BI dashboard.

## 2. Goals and non-goals

**Goals**
1. Reproduce the 3 confirmed issues exactly, and find and quantify every other data-quality problem in the 20 tables (rubric 1 → 4/4).
2. Use the right tool for each job and justify it in writing (rubric 2).
3. Put every artefact in Git, with unit, data, integration and regression tests and a 6-stage CI/CD pipeline plus monitoring (rubric 3).
4. Give each stakeholder numbers they can act on, in plain language, with **certain vs estimated** labels (rubric 4).
5. Show the deadline-driven prioritisation and the trade-offs (rubric 5).

**Non-goals**
- Fixing data in a real production system. Remediation is **designed, simulated on a copy, and gated**, but never applied to the source workbook.
- Contacting insurers to backfill. That is a documented remediation option, not something this project carries out.
- Patient-level clinical judgement. The project flags gaps; clinicians decide.

## 3. Key findings from initial profiling (2026-10-21)

These came from profiling `HCLS.xlsx` before any build work. They are the **test oracle**: the pipeline must reproduce these numbers, and regression tests pin them.

### 3.1 The brief's headline numbers vs the data

| Brief says | Data says | Implication |
|---|---|---|
| "Submitted $2.3M, received $1.8M, gap $500K" | For the **100 claims in `Approved` status**: submitted **$2,604,465.33**, approved/paid **$2,025,699.01**, gap **$578,766.32** | The brief's figures are rounded or stale. Report the data's figures and reconcile them to the brief in a footnote. |
| "90 of 250 claims missing approved_amount (36%)" | Confirmed: 90. **All 90** are `Submitted` (31), `Pending` (31) or `In Review` (28) | These claims **have not been adjudicated yet**, so a null approved amount is expected, not corrupt. They are **$2,225,289.25 of pipeline exposure**: an *estimated* figure, not lost revenue. This is the key judgement for Finance. |
| Total claims submitted | All 250 claims: **$6,066,812.08**, including 2 negative amounts (−$43,857.24 min) | Status breakdown: Approved $2.60M, Denied $1.08M, Pipeline $2.23M, Appealed $0.16M |
| "123 of 400 visits missing appointment link" | Confirmed: 123 (30.75%) | Spread evenly from 2020 to 2026 (10–23 per year), so the cause is **systemic since go-live, not a recent break** |
| "40 of 206 medical records missing prescribed_meds" | Confirmed: 40 (19.4%), all stored as the literal text `None` | Present in 2023-2026 (the records table has few rows before 2024); a clinical owner must say whether `None` means "no medication" or "not captured" |

### 3.2 Additional issues found (beyond the 3 confirmed)

The rule engine (`python -m hcls dq`) is the source of truth for these numbers; they were cross-checked against an independent pandas profile. 
**441 rules** run; **180 report findings** (164 excluding 16 'Info' fields that are empty by design). The scorecard in `docs/01_dq_scorecard.md` is generated from the same run.

**Hand-written business rules** (`sql/dq/*.sql`, listed in `src/hcls/dq/registry.yaml`) - failing records / records in scope:

| ID | Table | Issue | Severity | Failed / checked |
|---|---|---|---|---|
| A01 | Insurance_Claims | billing_id reused by more than one claim | High | 89 / 250 |
| A02 | Insurance_Claims | claim patient differs from the patient on the linked bill | Critical | 250 / 250 |
| A03 | Insurance_Claims | submitted_amount larger than the linked bill total | High | 244 / 250 |
| A04 | Insurance_Claims | approved_date earlier than submitted_date | Medium | 81 / 160 |
| A05 | Insurance_Claims | paid_date earlier than submitted_date | Medium | 52 / 100 |
| A07 | Insurance_Claims | negative submitted_amount | High | 2 / 250 |
| A08 | Insurance_Claims | Denied claim without a denial_reason | Medium | 5 / 50 |
| A09 | Billing | insurance_covered + patient_responsibility does not equal total_amount | High | 7 / 250 |
| A10 | Billing | amount_paid larger than patient_responsibility | High | 4 / 250 |
| A11 | Billing | negative total_amount | High | 3 / 250 |
| A12 | Billing | bill raised for a Cancelled or No-Show appointment | High | 81 / 249 |
| A13 | Billing | billing_date after due_date | Medium | 110 / 250 |
| A16 | Patients | duplicate patient_id | High | 55 / 4,861 |
| A17 | Patients | duplicate e-mail address (valid e-mails only) | Medium | 5 / 4,805 |
| A24 | Admissions | discharge_date earlier than admit_date | High | 152 / 289 |
| A25 | Appointments | updated_at earlier than created_at | Low | 47 / 107 |
| A28 | Prescriptions | end_date earlier than start_date | High | 118 / 293 |
| A29 | Prescriptions | marked active although end_date has passed | Medium | 153 / 197 |
| A30 | Prescription_Administration | administration patient differs from the prescription patient | Critical | 400 / 400 |
| A31 | Prescription_Administration | administered unit differs from prescribed unit | High | 349 / 400 |
| A32 | Prescription_Administration | given before the prescription start_date | Medium | 152 / 400 |
| A33 | Procedure_Codes | procedure code hierarchy contains a cycle | Medium | 3 / 45 |
| A34 | Referrals | doctor referred to themselves | Medium | 6 / 200 |
| A36 | Hierarchy | entity_id is not numeric (mixed key types) | Low | 21 / 641 |
| A37 | Patient_Insurance | coverage_end earlier than coverage_start | Medium | 22 / 300 |
| A38 | Patient_Insurance | linked claim belongs to a different patient | High | 230 / 230 |
| A39 | Nurses | nurse supervises themselves | Low | 2 / 107 |
| A40 | Nurse_Assignments | same nurse assigned twice on the same date | Medium | 7 / 350 |
| A41 | Visits | systolic_bp not greater than diastolic_bp | Medium | 3 / 400 |
| A43a | Hospitals | duplicate phone number | Low | 1 / 25 |
| A43b | Departments | duplicate phone extension | Low | 1 / 21 |
| A43c | Doctors | duplicate licence number | Medium | 1 / 620 |
| A44 | Insurance_Claims | approved_amount larger than submitted_amount | High | 2 / 160 |
| A45 | Insurance_Claims | paid_date earlier than approved_date | Medium | 61 / 100 |
| A49 | Patients | bmi inconsistent with height and weight | Low | 0 / 4,431 |
| A53 | Patients | last_visit_date earlier than registration_date | Low | 55 / 4,195 |
| C01 | Insurance_Claims | approved_amount missing | Critical | 90 / 250 |
| C02 | Visits | appointment_id missing (visit not linked to an appointment) | Critical | 123 / 400 |
| C03 | Medical_Records | prescribed_meds missing (stored as the text "None") | Critical | 40 / 206 |

**Generated rule families** (templates in `src/hcls/dq/rules.py`):

| ID pattern | What it checks | Rules | With findings |
|---|---|---:|---:|
| `N-<table>-<col>` | Missing values (every column of every table) | 217 | 61 |
| `R-<child>-<col>` | Foreign-key orphans (39 relationships) | 39 | 23 |
| `F-<table>-<col>` | Invalid format: dates, times, phones, e-mails, policy / group numbers, ICD-10 | 40 | 9 |
| `S-<table>-<col>` | Placeholder dates (1800-01-01, 1900-01-01, 2099-01-01 ...) | 27 | 4 |
| `P-<table>-<col>` | One date repeated 20+ times (default value) | 27 | 3 |
| `T-<table>-<col>` | Dated after the as-of date | 22 | 19 |
| `V-<table>-<col>` | Spelling / case / abbreviation variants in categories | 9 | 9 |
| `B-<table>-<col>` | Impossible numeric values (cleaned to blank) | 7 | 7 |
| `X-<table>-<col>` | Out-of-range values (flagged, never changed) | 12 | 7 |
| `J-<table>-<col>` | Invalid JSON | 2 | 0 |

Corrections to the first draft of this spec (v1.0), found while building the engine:

- **Referential_Integrity sheet over-reports two lines.** `Patients.primary_care_doctor_id` is listed with 500 violations; the true number is **0** (the sheet compared text such as `'379'` with numeric ids). `Patients.hospital_id` is listed with 31 violating values; the true number is **6** (81 rows). The scorecard uses recomputed values (DECISIONS D-010). v1.0 of this spec had copied the 500 as issue A23; that item is withdrawn.
- **C03 is the literal text `None`.** All 40 'missing' prescribed_meds values are the 4-letter text `None`, not empty cells. pandas silently turns `None` into a blank, which is why the brief counts them as missing. The ingest step now reads the workbook without that conversion (D-008). Whether `None` means "no medication prescribed" or "not captured" is an open question for the clinical owner; the brief treats it as missing, so we do too.
- **Duplicate e-mails:** v1.0 said 131. Of those, 126 were the placeholder text `not-an-email` / `user@.com` (a format problem, rule `F-Patients-email`); only **5** are genuine duplicate valid addresses (A17).
- **Placeholder dates found:** `1800-01-01` (58 dates of birth), `1900-01-01` (58 last-visit dates), `2099-01-01` (6 prescription starts, 3 appointment dates), `2025-13-01` (47 registration dates, month 13), plus text dates `tomorrow` (55) and `not available` (46).
- **Repeated 'default' values:** `01-01-2020` x50 (registration), `01/15/1987` x48 (date of birth), `2025-01-01` x50 (date of birth) - rule `P-*`.
- **Disguised blanks:** `N/A` (emergency contact name 73, employer 67, chronic conditions 58), `UNKNOWN` (last name 55, current medications 69) and `Null` (allergy 64) are treated as missing; `None` in allergy, surgery, family-history, alcohol, complications and accreditation columns is a valid answer and is kept.

> **Critical judgement:** A02, A03 and A30 show that the `Insurance_Claims.billing_id` and `Prescription_Administration.prescription_id` foreign keys do not join to the right records. **Do not use the claims→billing join to answer the overcharging question.** Report it as "cannot be determined from current data, because the link is broken" and treat that broken link as the root cause. Any number produced through that join would be wrong but look credible, which is the worst outcome for an audit.

> **As-of date:** every "future date" rule uses `AS_OF_DATE = 2026-10-21`, set in `config.yaml`, never `today()`. Without that, counts would drift and break regression tests.

## 4. Architecture and tool selection (rubric 2)

```
HCLS.xlsx ──► ingest (Python/pandas) ──► bronze/*.parquet (raw, all strings)
                                     └──► silver/*.parquet (typed, standardised, flagged; never deletes rows)
                    DuckDB SQL ◄──────────┘
                       │
         ┌─────────────┼───────────────────┬──────────────────────┐
         ▼             ▼                   ▼                      ▼
  DQ scorecard   Root-cause evidence   Finance recon (Excel)   Audit metrics
  (Phase 1)      (Phase 2)             (Phase 3)               (Phase 5)
         └─────────────┴───────── gold/*.parquet + CSV ───────────┘
                                         │
                                  Power BI (.pbix)

Scheduling: databricks/jobs/*.json (Databricks Workflows definitions; same SQL/Python)
CI/CD:      GitHub Actions — lint → unit → data → integration → approval → deploy
```

| Task | Tool | Why |
|---|---|---|
| Aggregations, null counts, FK checks, reconciliation totals | **SQL (DuckDB locally; Databricks SQL-compatible syntax)** | Set-based, readable to reviewers, and ports directly to Databricks |
| Ingest, type coercion, mixed-format dates, JSON address parsing, cycle detection, Excel writing | **Python 3.11 (pandas, openpyxl, pyyaml)** | Row-level and graph logic is awkward in SQL |
| Scheduling and automation | **Databricks Workflows** (job JSON + notebooks in `databricks/`) | Required by the brief; local runs use the same entry points via `make` / CLI |
| Testing | **pytest** (+ `pytest-cov`) | Covers unit, data-validation, integration and regression tests |
| Lint and format | **ruff** (Python), **sqlfluff** (SQL, `duckdb` dialect) | CI stage 1 |
| CI/CD | **GitHub Actions** with an `environment: production` approval gate | Gives the 6 stages in the brief, including a manual approval |
| Stakeholder visuals | **Power BI** | Required by the brief; reads gold CSV/parquet |

**Why not Databricks for everything?** The Free Edition workspace is serverless only, with restricted internet, so the job definitions in `databricks/jobs/` are a design that could not be deployed there. The same SQL runs on DuckDB locally, in CI and on Databricks: a notebook runs the pipeline and saves the results as Delta tables (D-041). Records: `DECISIONS.md` (D-001, D-031, D-041).

## 5. Repository layout

```
Capstone 3/
├── README.md  SPEC.md  PLAN.md  DECISIONS.md  CHANGELOG.md
├── config.yaml                 # as_of_date, thresholds, scoring weights, paths
├── pyproject.toml  Makefile  .gitignore  .sqlfluff  .pre-commit-config.yaml
├── Resources/                  # HCLS.xlsx, HCLS.html (read-only inputs)
├── data/clean/HCLS_cleaned.xlsx  # the cleaned dataset (committed deliverable)
├── src/hcls/
│   ├── config.py   ingest.py   standardise.py   export_clean.py   reports.py
│   ├── dq/  rules.py  registry.yaml  runner.py  scorecard.py
│   ├── rootcause/  timeline.py  lineage.py  evidence.py          (Sprint 2)
│   ├── recon/  flash.py  claims.py  excel_export.py              (Sprints 1, 3)
│   ├── remediation/  backfill_sim.py  validators.py              (Sprint 4)
│   ├── audit/  metrics.py  audit_log.py                          (Sprint 5)
│   └── cli.py                  # `python -m hcls <command>`
├── sql/  dq/*.sql  recon/*.sql  rootcause/*.sql  audit/*.sql
├── databricks/  notebooks/*.py  jobs/*.json                      (Sprint 4)
├── tests/  unit/  data/  integration/  regression/
├── .github/workflows/  ci.yml  deploy.yml
├── powerbi/  measures.dax.md  theme.json  BUILD_GUIDE.md         (Sprint 5)
├── docs/  01_dq_scorecard.md  CLEANING.md  02_root_cause_report.md  03_finance_brief.md
│          04_remediation_plan.md  05_audit_pack.md  stakeholder_memos/  sprints/SPRINT_N.md
└── outputs/                    # generated, gitignored (bronze, silver, gold)
```

## 6. Data model

**Primary keys:** each table's `<entity>_id`. `Hierarchy.entity_id` has mixed types and is stored as a string.

**Foreign keys** (validated against the `Referential_Integrity` sheet, which also serves as an oracle):

| Child.column | → Parent |
|---|---|
| Patients.hospital_id, Doctors.hospital_id, Hierarchy.hospital_id | Hospitals |
| Patients.primary_care_doctor_id, Appointments.doctor_id, Medical_Records.doctor_id, Prescriptions.doctor_id, Admissions.attending_doctor_id, Patient_Procedures.doctor_id, Referrals.referring/referred_doctor_id, Departments.head/subhead_doctor_id | Doctors |
| Doctors.department_id, Hierarchy.department_id, Nurse_Assignments.department_id | Departments |
| *.patient_id (Appointments, Visits, Medical_Records, Billing, Prescriptions, Admissions, Insurance_Claims, Patient_Insurance, Referrals, Prescription_Administration, Patient_Procedures) | Patients |
| Visits.appointment_id, Medical_Records.appointment_id, Billing.appointment_id | Appointments |
| Insurance_Claims.billing_id | Billing |
| Patient_Insurance.claim_id | Insurance_Claims |
| Prescription_Administration.prescription_id | Prescriptions |
| Prescription_Administration.nurse_id, Nurses.supervisor_nurse_id, Nurse_Assignments.nurse_id | Nurses |
| Patient_Procedures.code_id, Procedure_Codes.parent_code_id | Procedure_Codes |
| Patient_Procedures.admission_id | Admissions |

**Layers**
- **bronze:** a copy of each sheet as written, every column a string, plus `_source_sheet`, `_row_num` and `_ingested_at`.
- **silver:** typed columns. Unparseable values become null and get a flag column `_<col>_invalid`. Gender values are mapped (`F`→`Female`, `Mle`→`Male`, …) through `standardise.py` and the raw value is kept. **Rows are never dropped.** Every row gets `_dq_flags` (a list of rule IDs).
- **gold:** scorecard, reconciliation and audit tables consumed by Excel and Power BI.

## 6a. Data cleaning (added in v1.1)

The dataset ships with deliberately messy columns. Cleaning is a first-class deliverable, not a side effect.

| ID | Requirement |
|---|---|
| FR0.1 | Produce `data/clean/HCLS_cleaned.xlsx`: the same 20 sheets and columns as the raw file, real data types (integers, decimals, true dates, booleans, text with leading zeros preserved), plus a `Cleaning_Summary` sheet. |
| FR0.2 | **Never drop or add a row.** Row counts per sheet are identical to the raw file (tested). |
| FR0.3 | **Fix format:** every date column becomes ISO `yyyy-mm-dd` (appointments keep the time); phones become `(ddd) ddd-dddd`; e-mails are lower-cased; whitespace is trimmed; spelling / case / abbreviation variants of categories are mapped to one canonical value (gender, blood type, marital status, smoking, alcohol, language, ethnicity, patient status, hospital city). |
| FR0.4 | **Blank what is impossible, never invent:** unparseable or placeholder dates (`not available`, `tomorrow`, `2025-13-01`, `1800-01-01`, `1900-01-01`, `2099-01-01`), future dates of birth, heights / weights / BMI outside plausible limits, ratings above 5, negative experience or fees, SpO2 outside 50-100, malformed e-mails, phones, policy / group numbers and ICD-10 codes, and text placeholders (`N/A`, `UNKNOWN`, `Null`) become blank. |
| FR0.5 | **Compute only BMI**, from height and weight, when it is blank or was blanked. Nothing else is imputed. |
| FR0.6 | **Never change money, doses, clinical vitals or foreign keys.** They are flagged by the DQ engine instead, because changing them would hide evidence that auditors need. |
| FR0.7 | **Every change is logged** with table, Excel row number, column, old value, new value and rule (`outputs/gold/change_log.csv`); `docs/CLEANING.md` summarises them. |
| FR0.8 | **Prove it:** re-run the full rule set on the cleaned data. Every format / placeholder / domain / bounds rule must pass (0 failures); every business rule still failing is, by design, left for source-system or business fixes. Cleaning must not change C01, C02, C03, A02 or A30 (tested). |
| FR0.9 | Cleaning is **idempotent**: cleaning the cleaned data changes nothing (tested). |

Judgement calls are recorded in `DECISIONS.md` (D-007, D-008, D-009, D-012) and listed in `docs/CLEANING.md`.

## 7. Functional requirements by phase

### Phase 1: Data quality scope (scorecard)

- **FR1.1** A rule registry (`dq/registry.yaml`) where each rule has `id`, `table`, `column(s)`, `type` (completeness | validity | uniqueness | referential | consistency | timeliness), `severity` (Critical/High/Medium/Low), `stakeholder` (Finance/Compliance/PatientCare/Ops), `sql_file` or `python_fn`, `expected_baseline`.
- **FR1.2** It covers at least: **C01** claims approved_amount null, **C02** visits appointment_id null, **C03** MR prescribed_meds missing, the hand-written business rules in §3.2, a missing-value check on every column of all 19 data tables, every foreign key in §6, and format / placeholder / domain / range checks on every date, phone, e-mail, category and numeric column.
- **FR1.3** `gold/dq_scorecard` columns: `rule_id, table, column, check_type, severity, stakeholder, rows_checked, rows_failed, pct_failed, impact_statement, first_seen, last_seen, run_ts, git_sha`.
- **FR1.4** Timeline: for every rule on a dated table, the failures per year/quarter (`gold/dq_timeline`). This answers "when did it start?"
- **FR1.5** Severity ranking: impact score = severity weight × pct_failed × stakeholder weight. Top 10 go in the summary.
- **FR1.6** Results are appended to `gold/dq_history` (keyed by run timestamp) so trends show up in Power BI.
- **FR1.7** If any Critical rule exceeds `alert_threshold_pct` (default 5%), write an alert record (and, in Databricks, notify by email/Slack).

### Phase 2: Root cause diagnosis

- **FR2.1** For each Critical issue, produce a hypothesis tree covering the layers: source app / API / DB constraint / ETL. Record the evidence for and against each hypothesis, the diagnostic SQL, and a verdict (confirmed / likely / ruled out).
- **FR2.2** Evidence that must be produced:
  - C01: null pattern by `claim_status` (100% of nulls are non-final statuses), so the field is **not populated until adjudication**. This is a process/design issue, not corruption.
  - C02: null rate is flat across years and does not correlate with patient, hospital or visit notes, which points to **walk-in/unscheduled visits with no appointment captured, and no NOT NULL / FK constraint** at the source.
  - C03: null rate by year and doctor, and the share of those records where Prescriptions has an active Rx for the same patient (a backfill candidate).
  - A02/A03/A30: the join-key mismatch rate is 100% or close to it, which points to **an ETL key-mapping bug** (surrogate keys reassigned, or a positional join). Show sample row pairs as evidence.
  - Sentinel IDs (0, −1, 88888, 999, 9999x): test-data or default-value leakage, which means **no FK enforcement**.
- **FR2.3** `gold/rootcause/lineage.csv` (implemented in Sprint 2): a table → upstream-layer map, and a Mermaid diagram in `docs/02_root_cause_report.md`.
- **FR2.4** Interview guide (questions for the claims team and the ETL owner) and an ETL log checklist. The brief requires these, and they can't be done with data alone.

### Phase 3: Finance reconciliation (P0, Wednesday 5 PM)

- **FR3.1** Claim-level reconciliation based on `Insurance_Claims` only (see the judgement in §3.2). Each claim is put in one bucket:

| Bucket | Rule | Confidence |
|---|---|---|
| Paid | status = Approved and paid_date not null | **Certain** |
| Adjustment (contractual write-down) | submitted − approved for paid claims | **Certain** (amount); reason **Estimated** |
| Denied | status = Denied | **Certain** (amount); recoverability **Estimated** |
| Under appeal | status = Appealed | **Estimated** |
| Pipeline (unadjudicated) | status ∈ {Submitted, Pending, In Review}, approved null | **Estimated**, with an expected value = pipeline × P(approved) × approval ratio (≈ 75.3% on paid claims after holds; 77.8% as recorded), and a seeded 90% range. Pipeline × ratio alone is the **ceiling** (no denials), D-022 |
| Data-quality hold | negative amounts, approved above submitted, paid date after the as-of date (4 claims). Date-order problems alone are flagged but stay in their bucket (D-021) | **Excluded**, listed separately |

- **FR3.2** Every dollar ties out: Σ(buckets) = Σ submitted_amount ($6,066,812.08). A test asserts this.
- **FR3.3** Excel output `outputs/finance/CloneStream_Claims_Reconciliation_<as_of>.xlsx`, generated by code only:
  - **`Claims Summary`**: bucket totals, counts, confidence column, approval ratio, a reconciliation to the brief's $2.3M/$1.8M figures, and an assumptions block.
  - **`Customer Detail`**: one row per claim with patient_id, claim_number, status, submitted, approved, gap, bucket, confidence, DQ flags.
  - **`DQ Exceptions`**: rows held out, with the reason.
  - **`Read Me`**: definitions, as-of date, git SHA, run timestamp.
  - Formatting: number formats, frozen headers, autofilter, and conditional colour on the confidence column.
- **FR3.4** A one-page plain-language finance brief (`docs/03_finance_brief.md`): the number, what's certain, what's estimated, what we can't say yet, and why.

### Phase 4: Validation and remediation plan

- **FR4.1** Remediation per issue: **backfill** (source, method), **quarantine/flag**, **standardise**, or **accept as by-design** (e.g. C01). Each gets an owner, effort, risk and rollback.
- **FR4.2** Backfill simulation on a copy (`remediation/backfill_sim.py`), for example C03 from Prescriptions (same patient, Rx active on record_date), with a before/after row count and a match-confidence score. **The source workbook is never changed.**
- **FR4.3** Prevention validators (`remediation/validators.py`) usable at ingest: NOT NULL, FK, range, date-order and enum checks. These are the checks that would have caught each issue.
- **FR4.4** Databricks job design: `databricks/jobs/dq_daily.json` (02:00 UTC daily), `recon_weekly.json`, `audit_nightly.json`, with retries, timeout, email/Slack on failure, and a 5-minute SLA on recon.
- **FR4.5** Senior DE review checklist (`docs/04_remediation_plan.md` §Sign-off): staging run evidence, rollback steps, approval record.

### Phase 5: Audit-ready documentation and dashboard

- **FR5.1** `docs/05_audit_pack.md`: scope, method, scorecard, root causes, finance reconciliation, remediation, prevention, monitoring, open questions, and answers to all **8 Key Questions** in the brief.
- **FR5.2** *(implemented, D-035)* Audit trail: `gold/audit_log` with one row per pipeline run (run_id, job, git_sha, user, start/end, rows in/out, rules passed/failed, output hashes).
- **FR5.3** *(tables, measures, theme and build guide delivered; the `.pbix` is built in Desktop, D-037)* Power BI report `powerbi/CloneStream_DQ.pbix` with 5 pages:
  1. **Executive overview**: KPI cards (critical issues, overall DQ score, $ gap, $ pipeline), and a certain vs estimated split.
  2. **DQ scorecard**: rules by table/severity with drill-through, and a heatmap of table × check type.
  3. **Timeline**: failures over time per rule, which shows "systemic since 2020".
  4. **Finance reconciliation**: bucket waterfall from submitted to paid, and a confidence legend.
  5. **Patient care & compliance**: records missing meds/follow-up, the overcharge-question status, and the remediation tracker.
  Measures are documented in `powerbi/measures.dax.md`. The data source is gold CSV, with scheduled refresh documented.
- **FR5.4** Stakeholder memos (Finance, Compliance, Patient Care), each one page in plain language with no jargon.

## 8. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR1 | **Reproducible:** one command `make all` (or `python -m hcls all`) rebuilds every output from `Resources/HCLS.xlsx` |
| NFR2 | **Deterministic:** fixed `AS_OF_DATE` and no `today()` calls; outputs are stable for a given commit |
| NFR3 | **Performance:** the full pipeline runs in < 2 min locally; recon in < 5 min (brief SLA) |
| NFR4 | **Non-destructive:** the source is read-only; silver keeps every row; remediation runs only on copies |
| NFR5 | **Traceable:** every output carries `run_ts`, `git_sha` and `as_of_date` |
| NFR6 | **Privacy:** no PII (names, emails, phones, addresses) in committed outputs or Power BI visuals beyond IDs |
| NFR7 | **Quality bar:** ruff and sqlfluff clean; test coverage ≥ 80% on `src/hcls` |

## 9. Testing strategy

| Type | Location | What it proves | Examples |
|---|---|---|---|
| Unit | `tests/unit` | Functions behave on hand-built inputs | date parser handles `01/15/1987` and `not available`; gender mapper; cycle detector finds 2↔3; bucket classifier |
| Data validation | `tests/data` | Each DQ rule **catches a planted defect and passes clean data** | the fixture `mini_hcls.xlsx` has 1 known defect per rule; assert exact counts |
| Integration | `tests/integration` | End-to-end on the fixture: ingest → silver → scorecard → Excel | Excel has 4 named sheets; bucket sum = submitted sum |
| Regression | `tests/regression` | Real-data baselines in §3 stay pinned | C01 = 90, C02 = 123, C03 = 40, Approved gap = 578,766.32, total = 6,066,812.08, A02 = 250 |

Rules: the build fails if any test fails, and no test is skipped without a `DECISIONS.md` entry.

## 10. CI/CD pipeline (`.github/workflows/ci.yml`, `deploy.yml`)

| # | Stage | Job | Gate |
|---|---|---|---|
| 1 | Code quality | `ruff check`, `ruff format --check`, `sqlfluff lint sql/`, yaml/json schema check of job files | must pass |
| 2 | Unit tests | `pytest tests/unit` | must pass |
| 3 | Data tests | `pytest tests/data` on the fixture | must pass |
| 4 | Integration | `pytest --cov=src/hcls --cov-fail-under=80` (all suites incl. integration and regression on the full HCLS.xlsx); upload outputs as a build artefact | must pass, coverage ≥ 80% |
| 5 | Approval gate | GitHub `environment: production` with a required reviewer | manual sign-off |
| 6 | Deploy | (simulated) `databricks jobs reset --json-file …` dry-run, publish gold CSVs + Excel to release artefacts, tag release | on `main` only |

Triggers: every PR to `main` runs stages 1–4. A merge to `main` runs 1–6.

## 11. Monitoring and alerts

- Job success/failure goes to email/Slack (Databricks job `email_notifications` / `webhook_notifications`; locally and in CI, `python -m hcls notify` posts to a Slack incoming webhook, plus a log line and `outputs/alerts.json`). Implemented in `monitoring/notify.py`, DECISIONS D-040).
- **Threshold alert:** any Critical rule with pct_failed > 5% alerts Finance (configurable).
- **Drift alert:** a rule's failure count changes by more than 10% between runs.
- **Performance:** recon duration logged, and an alert fires if it exceeds 5 min.
- **Audit trail:** `gold/audit_log` (FR5.2).

## 12. Acceptance criteria mapped to the rubric

| Rubric dimension (0–4) | What earns 4 here | Evidence |
|---|---|---|
| 1. Discovery & analysis | C01–C03 exact, plus 40+ additional issues with counts, % and impact, plus a timeline | `docs/01_dq_scorecard.md`, `gold/dq_scorecard`, `gold/dq_timeline` |
| 2. Tools & implementation | Tool-choice table (§4) with justification; `make all` runs clean | README, CI green |
| 3. Git, tests, CI/CD | Meaningful conventional commits, all 4 test types passing, 6-stage pipeline, monitoring | `.github/workflows`, `tests/`, git log, PR history |
| 4. Business logic & communication | Certain vs estimated on every number; stakeholder memos; trade-offs stated | Excel `Claims Summary`, `docs/stakeholder_memos/` |
| 5. Pressure & judgement | Finance-first sequencing; "good enough" calls logged; the claims→billing join refused with reasons | `DECISIONS.md`, `PLAN.md` timeline |

## 13. Answers the project must deliver (brief's 8 Key Questions)

| # | Question | Expected answer shape (to be confirmed by Phase 2 evidence) |
|---|---|---|
| 1 | Where did it break? | Per issue: C01 is process/design (not a break); C02/C03 are missing source constraints; A02/A30 are an ETL key-mapping bug; sentinels are a lack of FK enforcement |
| 2 | When did it start? | Missing-value rates are flat from 2020 to 2026, so the problem is **systemic from the start, not a recent incident** |
| 3 | How many more issues? | 441 rules run; 164 report findings beyond the 3 confirmed (§3.2), ranked by impact in `docs/01_dq_scorecard.md` |
| 4 | Is it systemic? | Multiple independent failures with one common cause: **no validation at ingest** |
| 5 | Can we fix it? | **Not by backfill** (simulated: 0 of 40 C03, 0 of 123 C02 recoverable safely, D-028). C01 resolves through adjudication or insurer remittance (835); C02/C03 need source constraints plus human review; broken FKs need a fix to the source key mapping |
| 6 | Should we refund? | **Can't be determined yet**, because the claims→billing link is unreliable. Recommend a hold, then re-run after the key fix |
| 7 | Confidence level? | Certain: $1.95M paid, $0.64M adjustment, $1.12M denied (after 4 held claims). Estimated: $2.23M pipeline (≈ $1.17M expected, range $1.04M-$1.30M; $1.68M ceiling), $0.16M appeals |
| 8 | How to prevent? | Ingest validators (FR4.3), DB constraints, a daily DQ job with thresholds, and data contracts with the claims system |

## 14. Constraints for the coding agent (opencode)

- Read and write **only inside the `Capstone 3` folder**. Never modify `Resources/`.
- **Never run `git push`, `git merge` into `main`, or open PRs.** The agent may stage files and suggest commit messages; Manas runs the git commands.
- Every sprint ends by updating `README.md` (status, how to run, outputs), `CHANGELOG.md` and `DECISIONS.md`.
- If the data contradicts this spec (a count differs from §3), **stop, log it in `DECISIONS.md`, and update the spec**. Don't silently change tests to match.
