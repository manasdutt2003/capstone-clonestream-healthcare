# CloneStream Healthcare Data Crisis - Capstone 3

[![CI](https://github.com/<your-user>/<your-repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-user>/<your-repo>/actions/workflows/ci.yml)

Perficient Global AI First Academy, GGTP_BLR_DP_SEP_26, Week 4 individual capstone. Owner: **Manas Dutt**.

CloneStream Healthcare found data-integrity problems in claims, visits and medical records, with a **Finance deadline on Wednesday 5 PM** and **auditors on-site Friday**. This repository finds out what is broken, cleans the data, reconciles the money, plans the fix and packages the evidence. Everything is code, versioned, tested and rebuilt with one command.

## Status

| Sprint | Phase | Branch | Tag | Status |
|---|---|---|---|---|
| 1 | Understand the scope (+ data cleaning) | `sprint-1-dq-scope` | `v1.0` | **Done** |
| 2 | Diagnose root cause | `sprint-2-root-cause` | `v2.0` | **Done** |
| 3 | Finance reconciliation | `sprint-3-finance-recon` | `v3.0` | **Done** |
| 4 | Validate and plan remediation | `sprint-4-remediation` | `v4.0` | **Done** |
| 5 | Audit-ready documentation | `sprint-5-audit-pack` | `v5.0` | **Done** |

Documents: [SPEC.md](SPEC.md) (what) | [PLAN.md](PLAN.md) (when) | [DECISIONS.md](DECISIONS.md) (why) | [CHANGELOG.md](CHANGELOG.md)

## What we know so far (Sprints 1-5)

| Question | Answer |
|---|---|
| Are the brief's 3 issues real? | Yes, exactly: **90 / 250** claims without an approved amount (36%), **123 / 400** visits without an appointment (30.75%), **40 / 206** medical records with no prescribed medication (19.4%). |
| What are the 90 blank approved amounts? | **Claims the insurer has not decided yet** (31 Submitted, 31 Pending, 28 In Review). Not lost data. They hold **$2,225,289** of claims. We expect about **$1.17M** to be approved (range $1.04M-$1.30M); $1.68M is the ceiling if nothing were denied. 78 of the 90 are over a year old. |
| What did Finance actually get paid? | **$1,945,489 (certain)** on 97 approved claims asked at $2,582,390 (reduced by $636,901). A further $80,210 on 3 approved claims is held because the data is impossible; as recorded the 100 approved claims show $2,025,699. The brief's $2.3M / $1.8M do not match the data. |
| Where does every claim dollar sit? | Paid $1.95M, adjustment $0.64M, denied $1.12M, under appeal $0.16M, pipeline $2.23M, held 4 claims. They **tie to $6,066,812.08 to the cent**. See [docs/03_finance_brief.md](docs/03_finance_brief.md). |
| Were patients over-charged? | **Cannot be said yet.** The claim -> bill link is wrong on 250 / 250 claims. A number built on it would look precise and be wrong. |
| Is it a recent break? | No. C01 and C02 have the **same failure rate in all 7 years** (p = 0.96 and 0.50); C03 cannot be dated (94% of records are from 2024 on). A **design gap**, not an incident. |
| Where did it break? | C01: nowhere, it is by design (blank until the insurer decides). C02 / C03: the **source application** does not force a link or a medicine entry. Cross-table links: **ETL key mapping** plus no foreign-key enforcement. 14 hypotheses tested, verdicts in the report. |
| Which links can be trusted? | Only **Billing -> Appointments** (248 of 249 same patient). Visits -> Appointments 1 of 277; Claims -> Billing 0 of 250; Rx administration -> Prescriptions 0 of 400. 10 of 39 links are broken, 12 degraded, 17 healthy. |
| Where do the placeholder patient ids come from? | 116 rows in 8 tables; 12 of 13 orphan bills inherit the id from their appointment, so it starts **upstream** in the appointment system. |
| How many other problems? | 441 rules run; **164 report findings** (5 Critical, 23 High, 73 Medium, 63 Low). See [docs/01_dq_scorecard.md](docs/01_dq_scorecard.md). |
| Can the data be backfilled? | **No.** Simulated on a copy: **0 of 40** medical records and **0 of 123** visits can be filled safely (no matching prescription or appointment, or the match contradicts the plan). Fix at the source and review by hand. Plan: [docs/04_remediation_plan.md](docs/04_remediation_plan.md). |
| What would have prevented it? | **49 ingest validators**; they would reject 1,903 rows. Daily alerts fire on 5 Critical rules and are posted to Slack (`python -m hcls notify`; needs a webhook, see [docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md)). The pipeline also runs as a scheduled job on Databricks Free Edition (D-041). |
| Can an auditor trust the outputs? | Every run is logged (who, when, code version, result) and every output has a SHA-256 in `audit_outputs.csv`; `make verify` fails if one was edited. Full answers to the brief's eight questions: [docs/05_audit_pack.md](docs/05_audit_pack.md). |
| Is the workbook's own integrity sheet right? | Mostly. **Two lines over-report** (it compared text ids with numeric ids). |

Audit pack (start here if you are an auditor): [docs/05_audit_pack.md](docs/05_audit_pack.md). Memos: [Finance](docs/stakeholder_memos/01_finance_memo.md), [Compliance](docs/stakeholder_memos/02_compliance_memo.md), [Patient Care](docs/stakeholder_memos/03_patient_care_memo.md). Power BI build guide: [powerbi/BUILD_GUIDE.md](powerbi/BUILD_GUIDE.md).

Finance Flash for the CFO: [docs/stakeholder_memos/00_finance_flash.md](docs/stakeholder_memos/00_finance_flash.md)

Finance brief and workbook: [docs/03_finance_brief.md](docs/03_finance_brief.md); the workbook is `outputs/finance/CloneStream_Claims_Reconciliation_2026-10-21.xlsx` (regenerate with `python -m hcls recon`).

Root-cause report (timeline, link health, lineage map, hypotheses, interview guide): [docs/02_root_cause_report.md](docs/02_root_cause_report.md)

## Cleaned dataset

`data/clean/HCLS_cleaned.xlsx` - same 20 sheets and columns, **no rows dropped**, real data types, ISO dates, standard phone / category formats, plus a `Cleaning_Summary` sheet. 3,156 cells changed; every change is in `outputs/gold/change_log.csv`. Rules and judgement calls: [docs/CLEANING.md](docs/CLEANING.md).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
make all          # ingest -> clean -> dq -> flash -> rootcause -> recon -> backfill -> validate -> alerts -> notify -> audit -> powerbi -> docs   (about 18 seconds)
make test         # 349 tests
make lint         # ruff + sqlfluff
```

No `make` on Windows? Use `python -m hcls all`, `pytest`, `ruff check src tests`, `sqlfluff lint sql --dialect duckdb`.

| Command | What it does |
|---|---|
| `python -m hcls ingest` | Read the 20 sheets as text into `outputs/bronze/` |
| `python -m hcls clean` | Standardise to `outputs/silver/`, write the change log and `data/clean/HCLS_cleaned.xlsx` |
| `python -m hcls dq` | Run all rules on raw and cleaned data; write the scorecard, timeline, history, cross-checks to `outputs/gold/` |
| `python -m hcls flash` | Write the Finance Flash |
| `python -m hcls backfill` / `validate` / `alerts` | Backfill simulation on a copy; ingest validators and catch report; threshold, drift and SLA alerts |
| `python -m hcls notify` | Post the alerts to Slack (dry run if no webhook is set); `--job NAME --status failed` posts a job status; see [docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md) |
| `python -m hcls.deploy.validate_jobs` / `.dry_run` | Check Databricks job definitions; print the deploy plan (deploys nothing) |
| `python -m hcls audit` / `powerbi` | Audit metrics and output fingerprints; PII-free tables for Power BI in `outputs/powerbi/` |
| `python -m hcls.audit.verify` (`make verify`) | Exit 1 if any gold output changed since the last audit run |
| `python -m hcls docs` | Regenerate `docs/01_dq_scorecard.md` and `docs/CLEANING.md` |

## Run on Databricks (Free Edition)

Two notebooks in [databricks/notebooks/](databricks/notebooks/): `00_setup.py` creates the schema `workspace.clonestream` and a volume `raw`; `01_run_pipeline.py` unzips the project zip from the volume, runs `python -m hcls all`, and saves every output as a Delta table (78 tables). It runs as the scheduled job `Capstone_4`. The check cell should show 20 sheets, 10,203 rows, 0 rows dropped, 164 findings and 5 Critical. The computation is still DuckDB and pandas on one machine; Delta only stores the results. Steps and limits: [databricks/README.md](databricks/README.md), decision D-041.

## How it works

```
Resources/HCLS.xlsx --ingest--> bronze (text, lineage) --standardise--> silver (clean text, nothing dropped)
                                    |                                      |
                                    +---------- DuckDB rule engine --------+
                                         441 rules -> scorecard, timeline, history
                                                     |
                      +------------------------------+-------------------------+
                      v                              v                         v
              docs/01_dq_scorecard.md        data/clean/HCLS_cleaned.xlsx   Finance Flash
```

| Task | Tool | Why |
|---|---|---|
| Counting, joins, reconciliation | **SQL on DuckDB** (`sql/`) | Set-based and readable; ports to Databricks SQL |
| Parsing, cleaning, graph checks, Excel output | **Python / pandas** | Row-level logic is awkward in SQL |
| Scheduling (Sprint 4) | **Databricks Workflows** job definitions | Required by the brief. The pipeline ran on Databricks Free Edition (D-041); the job JSON stays a design (D-001, D-031) |
| Tests | **pytest** | Unit, data-validation, regression, integration |
| Quality gates | **ruff, sqlfluff, GitHub Actions** | Six-stage pipeline |

## Rules of the road

- **Nothing is deleted.** Cleaning blanks or reformats; row counts never change.
- **Money, doses and keys are never "fixed".** They are flagged so auditors see the evidence.
- **Every number carries a confidence label:** certain or estimated.
- **`as_of_date` is fixed** (2026-10-21) so results are repeatable.

## Repository map

See SPEC.md section 5. Generated outputs go to `outputs/` (not committed). Committed deliverables live in `data/clean/` and `docs/`.

## Rubric self-assessment

| Dimension | Evidence | Where to check | Honest gaps |
|---|---|---|---|
| 1. Data discovery & analysis | 3 confirmed issues reproduced exactly; 164 findings from 441 rules; yearly timeline with a statistical test; 14 hypotheses with computed verdicts; link-health lineage map; interview guide | [scorecard](docs/01_dq_scorecard.md), [root cause](docs/02_root_cause_report.md) | Source-system groupings are inferred and need the ETL owner to confirm |
| 2. Tools & implementation | Tool table above with reasons; SQL on DuckDB, Python, ruff, sqlfluff, pytest, GitHub Actions; `make all` runs clean in about 18 s; pipeline run on Databricks Free Edition with results in Delta tables (D-041), job JSON and Power BI delivered as versioned definitions | [SPEC section 4](SPEC.md), [databricks/](databricks/README.md), [powerbi/](powerbi/BUILD_GUIDE.md) | The Databricks run uses the free edition: compute is DuckDB/pandas on one machine, Slack is a dry run there, and `databricks/jobs/` stays a design (D-001, D-041); the `.pbix` is built in Desktop from the guide (D-037) |
| 3. Git, tests, CI/CD | 349 tests (unit, data, integration, regression), 97% coverage; CI stages 1-6 with a `production` approval gate; alerts; audit log with output hashes; hyphenated sprint branches and tags `v1.0`-`v5.0` | [.github/workflows](.github/workflows), [tests/](tests), [CHANGELOG](CHANGELOG.md) | Deploy is simulated; the required reviewer must be set in GitHub settings |
| 4. Business logic & communication | Finance Flash corrected by the brief; reconciliation workbook that ties to the cent; certain vs estimated with a range; over-charging answered honestly; three one-page memos; audit pack answering the eight questions | [finance brief](docs/03_finance_brief.md), [audit pack](docs/05_audit_pack.md), [memos](docs/stakeholder_memos) | Paid total not yet confirmed against the insurer remittance |
| 5. Pressure & judgement | Finance-first sequencing; the claim-to-bill join refused; backfill rejected when it contradicted the treatment plan; 39 logged decisions and 9 open questions | [DECISIONS](DECISIONS.md), [PLAN](PLAN.md) | Effort estimates are planning guesses for owners to confirm |

## Outputs index

| Output | Command | Location |
|---|---|---|
| Cleaned dataset | `clean` | `data/clean/HCLS_cleaned.xlsx` |
| Scorecard, timeline, history | `dq` | `outputs/gold/dq_*.csv` |
| Root-cause evidence | `rootcause` | `outputs/gold/rootcause/` |
| Finance workbook | `recon` | `outputs/finance/` |
| Backfill, validators, alerts | `backfill`, `validate`, `alerts` | `outputs/gold/`, `outputs/alerts.json` |
| Slack message preview | `notify` | `outputs/slack_preview.json` |
| Audit log, metrics, manifest | `audit` | `outputs/gold/audit_*.csv` |
| Power BI tables | `powerbi` | `outputs/powerbi/` |
| Written reports and memos | `docs` | `docs/` |
