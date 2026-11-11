# Changelog

All notable changes, newest first. Versions match the git tags `vN.0` (one per sprint).

## Unreleased - Databricks run (2026-10-25)

### Added
- `databricks/notebooks/00_setup.py` and `01_run_pipeline.py`: run `python -m hcls all` on Databricks Free Edition and save 78 Delta tables in `workspace.clonestream`. Ran green as job `Capstone_4`; numbers match the local run (D-041).

### Changed
- README, SPEC, PLAN, DECISIONS (D-001, D-031 amended), `databricks/README.md`, `docs/NOTIFICATIONS.md` and the audit pack no longer say there is no Databricks workspace.

### Not done
- The Jobs API JSON in `databricks/jobs/` was not deployed (free edition). Compute is still DuckDB/pandas on one machine; Slack is a dry run on Databricks.

## Unreleased - Slack notifications (2026-10-22)

### Added
- `monitoring/notify.py` and `python -m hcls notify` (part of `make all`, right after `alerts`): posts the alerts, an all-clear, and job success / failure to Slack through an incoming webhook. Routes by stakeholder (`SLACK_WEBHOOK_URL_FINANCE` etc.), skips an unchanged alert set, retries, never fails the pipeline unless `--strict`, writes a dry-run preview to `outputs/slack_preview.json` when no webhook is set.
- Databricks: `webhook_notifications.on_failure` on all three jobs, a `notify` task at the end of `dq_daily`, the notebook posts a failed step to Slack, and `validate_jobs` requires the Slack destination.
- `deploy.yml` (and the root copies): the Slack secret is passed to the rebuild, and a success or failure message is posted at the end of the deploy.
- `docs/NOTIFICATIONS.md`: setup, routing, what is sent, how to test.
- Tests: 24 new (routing, messages, de-duplication, dry run, retries, no leaked URL, job destinations). Total 349; coverage 97%.

### Not done
- Not tested against a real Slack workspace (none was available); the HTTP path was tested against a local stand-in server. Send one test message first (see docs/NOTIFICATIONS.md).

## v5.0 - Sprint 5: Audit-ready documentation (2026-10-22)

### Added
- `python -m hcls audit | powerbi` (part of `make all`): audit metrics and an output manifest; PII-free Power BI tables.
- `audit/audit_log.py`: one audit row per pipeline command (also failures), SHA-256 manifest of every gold file, `python -m hcls.audit.verify` (`make verify`).
- `audit/metrics.py`: 20 headline metrics per run, appended to `gold/audit_metrics.csv` for trend charts.
- `audit/powerbi.py`: 18 tables for Power BI (facts, two dimensions, a waterfall) with a hard PII check.
- `powerbi/`: `measures.dax.md`, `theme.json`, `BUILD_GUIDE.md` (five pages, relationships, checks, refresh).
- `docs/05_audit_pack.md`: scope, the eight key questions, scorecard, root causes, money, remediation, prevention, audit trail, open questions and an evidence index; generated.
- `docs/stakeholder_memos/`: one-page memos for Finance, Compliance and Patient Care; generated.
- Tests: audit trail, tamper detection, PII refusal, waterfall, memos, pack, DAX references. Total 325; coverage 97%.

### Changed
- README: final status, rubric self-assessment with evidence links, outputs index.

## v4.0 - Sprint 4: Validate and plan remediation (2026-10-21)

### Added
- `python -m hcls backfill | validate | alerts` (all part of `make all`).
- `remediation/backfill_sim.py`: simulates the C03 and C02 backfills on a copy with confidence labels and a source fingerprint check.
- `remediation/validators.py`: 49 ingest validators and a catch report showing what each would have rejected.
- `remediation/plan.py` -> `docs/04_remediation_plan.md`: nine remediation groups covering all 28 Critical/High rules (action, owner, effort, risk, rollback, prevention), alerts, jobs and sign-off checklist.
- `monitoring/alerts.py`: threshold, drift and recon-SLA alerts to `outputs/alerts.json`; `dq` keeps `dq_scorecard_previous.csv` for drift.
- `databricks/`: three job definitions, a JSON schema, a step notebook; `hcls.deploy.validate_jobs` and `hcls.deploy.dry_run`.
- `.github/workflows/deploy.yml`: stage 5 approval gate, stage 6 simulated deploy and release. `ci.yml` validates the job definitions.
- `ci/root-workflows/`: generated copies for the repo-root `.github/workflows/`.
- Tests: validators, backfill, alerts, deploy, plan. Total 307+; coverage 97%.

### Findings
- Backfill recovers **0 of 40** C03 and **0 of 123** C02 records; fixes belong at the source plus human review.
- The validators would reject 1,903 distinct rows; 38 of 49 checks fire.
- 5 threshold alerts fire (the Critical rules).

### Changed
- SPEC Key Question 5 corrected (see D-028).

## v3.0 - Sprint 3: Finance reconciliation (2026-10-21)

### Added
- `python -m hcls recon` (also part of `make all`): claim-level reconciliation from `Insurance_Claims` only.
- `sql/recon/claims_buckets.sql` + `recon/claims.py`: Paid, Adjustment, Denied, Under appeal, Pipeline, Approved-not-yet-paid and DQ Hold buckets with a confidence label per claim; tie-out of every dollar; pipeline expected value with a seeded 90% range; pipeline aging; reconciliation to the brief; exceptions list.
- `recon/excel_export.py`: `outputs/finance/CloneStream_Claims_Reconciliation_<as_of>.xlsx` with `Claims Summary`, `Customer Detail`, `DQ Exceptions`, `Read Me` (number formats, frozen headers, autofilter, conditional colour on confidence).
- `recon/brief.py`: `docs/03_finance_brief.md`, the plain-language finance brief, including the over-charging answer and the data needed.
- `outputs/gold/recon_*.csv` and `recon_timing.csv` (runtime against the 5-minute limit).
- Tests: 37 new (classifier, holds, tie-out, expected value, aging, workbook structure, pinned real-data numbers, end-to-end run). Total 260; coverage 98%.

### Findings
- Every submitted dollar ties out: $6,066,812.08 across 250 claims.
- Certain: **Paid $1,945,489** (97 claims), Adjustment $636,901, Denied $1,123,431 (49 claims). Estimated: Pipeline $2,225,289 (90), Under appeal $157,484 (10). Held for review: 4 claims.
- **Correction to the Finance Flash:** the Flash's $1.73M for the open claims assumed no denials. The expected value is **$1.17M** (range $1.04M-$1.30M); $1.68M is the ceiling. The Flash's $2.03M paid included $0.08M on 3 approved claims with impossible data.
- 78 of the 90 open claims were submitted over a year ago, so the estimate may still be optimistic.
- 84 of the 97 paid claims have a date out of order: dates cannot be used for payment timing.
- The brief's $2.3M / $1.8M could not be reproduced; the data says $2.58M / $1.95M on paid claims.
- Over-charging: not determinable; recommend a hold on refunds.

### Changed
- Finance Flash wording: the pipeline figure is labelled a ceiling and the memo points to the new brief.

## v2.0 - Sprint 2: Diagnose root cause (2026-10-21)

### Added
- `python -m hcls rootcause` (also part of `make all`): writes `outputs/gold/rootcause/*.csv` and `docs/02_root_cause_report.md`.
- `rootcause/timeline.py`: failure rate by year and quarter for C01, C02, C03, A02, A30; chi-square test for a change over time; best before/after split.
- `rootcause/evidence.py` + 12 diagnostic queries in `sql/rootcause/`: C01 by claim status, link health, claim-vs-bill amounts and sample pairs, billing-id offset test, C02 and C03 breakdowns, placeholder-id analysis and propagation.
- `rootcause/lineage.py`: 39 foreign-key edges rated healthy / degraded / broken, drawn as a Mermaid map.
- 14 hypotheses with computed verdicts; plain-language answers to Key Questions 1-4; interview guide (claims team, ETL owner, clinical owner); ETL log checklist.
- Tests: 47 new (timeline statistics, lineage thresholds, planted-defect SQL, verdict logic, pinned real-data conclusions). Total 223; coverage 98%.

### Findings
- C01 is **status-driven**: all 90 blanks are Submitted / Pending / In Review; every decided claim has an amount. Confirmed expected behaviour.
- C01, C02 and C03 failure rates are **flat across years** (p = 0.96, 0.50, 0.18): a design gap, not an incident.
- Only Billing -> Appointments is a sound link (248 of 249 same patient). Visits -> Appointments 1 of 277; Medical_Records -> Appointments 0 of 177; Claims -> Billing 0 of 250; Patient_Insurance -> Claims 0 of 230; Rx administration -> Prescriptions 0 of 400.
- Shifting the claim -> bill join by up to 10 rows does not repair it; the median claim is 64x its bill; only 9 of 250 claim patients have any bill.
- 116 rows in 8 tables carry placeholder patient ids; 12 of 13 orphan bills inherit theirs from the appointment, so it originates upstream.
- C03: 20 of the 40 `None` records have a plan that names a drug; only 3 of 40 patients have any prescription (none from the same doctor).

### Changed
- Branch naming uses hyphens (D-015).

## v1.0 - Sprint 1: Understand the scope (2026-10-21)

### Added
- Project scaffold: `config.yaml` (fixed as-of date), `pyproject.toml`, `Makefile`, ruff / sqlfluff / pre-commit configuration.
- `ingest.py`: reads all 20 sheets as text into a bronze layer with lineage columns, without pandas NA conversion.
- `standardise.py` + `export_clean.py`: cleaning of dates, categories, phones, e-mails, identifiers and impossible values; full change log; `data/clean/HCLS_cleaned.xlsx` (same rows, real types).
- Data-quality engine: 441 rules (39 hand-written SQL / Python business rules plus generated missing-value, foreign-key, format, date, domain and range rules), scorecard with impact ranking, yearly timeline, run history.
- Cross-check of the workbook's `Referential_Integrity` sheet (two lines over-report).
- Finance Flash: one-page preliminary claims answer for the CFO.
- Tests: 176 (unit, data-validation, regression, integration); coverage 97%.
- GitHub Actions CI stages 1-4 (code quality, unit, data, integration + coverage gate).
- Docs: `SPEC.md`, `PLAN.md`, `DECISIONS.md`, `docs/01_dq_scorecard.md`, `docs/CLEANING.md`, `docs/stakeholder_memos/00_finance_flash.md`.

### Findings
- Confirmed: 90 / 250 claims without approved amount, 123 / 400 visits without appointment, 40 / 206 medical records with prescribed_meds `None`.
- 164 further rules report findings; the claim -> bill and administration -> prescription links are wrong on every row.
