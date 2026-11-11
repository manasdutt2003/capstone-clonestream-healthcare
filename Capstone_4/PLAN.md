# PLAN — CloneStream Healthcare Data Crisis (Capstone 3)

Version 1.5 (Sprint 5 delivered; Sprint 4 delivered; Sprint 3 delivered; Sprint 2 delivered; branch names use hyphens; sprint snapshots delivered as zips). Companion to `SPEC.md` (the *what*). This file covers **order, timing, branches and done-criteria**. Status is tracked in `README.md`.

---

## 1. Strategy in one paragraph

Finance's deadline (Wed 5 PM) comes before Compliance's (Fri). So the plan delivers a **defensible finance number first**, even though the brief numbers it Phase 3. Sprint 1 builds the foundation (ingest, DQ engine, CI) and ends with a **Finance Flash**: the claims status breakdown with certain/estimated labels, which can be drawn directly from Insurance_Claims without trusting any broken joins. Sprints 2–3 add root cause and the formal reconciliation workbook before Wednesday 5 PM. Sprints 4–5 turn everything into an audit pack before Friday. Each phase is one sprint, one branch and one PR.

## 2. Incident timeline (simulated week)

| When | Sprint | Milestone | Stakeholder outcome |
|---|---|---|---|
| Mon (Day 1) | S1 — Scope | Scorecard v1 + **Finance Flash** | Finance has preliminary numbers by end of day |
| Tue | S2 — Root cause | Root-cause report v1 | Engineering knows where it broke |
| **Wed by 5 PM** | S3 — Finance recon | **Reconciliation Excel + finance brief** | **CFO deadline met** |
| Thu | S4 — Remediation | Remediation plan, validators, Databricks jobs, sign-off | Senior DE approves the plan |
| **Fri AM** | S5 — Audit pack | Audit pack, Power BI, memos, release tag | **Auditors on-site: evidence ready** |

"Good enough" rule: if a sprint runs over, cut **breadth** (lower-severity rules, extra visuals), never **correctness** (tie-outs, confidence labels, tests on Critical rules). Log every cut in `DECISIONS.md`.

## 3. Git workflow (Manas runs these; the agent never pushes)

**Sprint zips.** Each `capstone3_sprint_N.zip` is a *complete snapshot of the repository at the end of sprint N*. To use one: on a new branch, unzip it over the project folder (overwrite when asked), then commit using the grouped commits in `docs/sprints/SPRINT_N.md`. Because each snapshot contains everything from earlier sprints, git only sees the new and changed files.

One-time setup:
```bash
cd "C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 4\Capstone 3"
git init -b main
git add README.md SPEC.md PLAN.md .gitignore
git commit -m "docs: add project spec, plan and readme skeleton"
git remote add origin <your-repo-url>
git push -u origin main
```
Then in GitHub: **Settings → Environments → `production`** → add yourself as a required reviewer (this is CI stage 5). Protect `main`: require PR + passing checks.

Per sprint:
```bash
git switch main && git pull
git switch -c sprint-N/<slug>
# ... agent works; review its diff ...
git add -A && git commit -m "<type>(<scope>): <summary>"   # several small commits, not one big one
git push -u origin sprint-N/<slug>
# open PR on GitHub → CI stages 1–4 must be green → self-review → squash or merge
git switch main && git pull
git tag -a vN.0 -m "Sprint N: <phase>" && git push --tags
```
Commit convention: `feat|fix|test|docs|ci|chore|refactor(scope): summary`. Example: `feat(dq): add referential integrity rules for 20 FK pairs`.

---

## 4. Sprints

### Sprint 1 — Phase 1: Understand the scope
**Branch:** `sprint-1-dq-scope` · **Tag:** `v1.0` · **Spec:** §3, §5, §6, FR1.x, §9, §10

| # | Task | Output |
|---|---|---|
| 1.1 | Scaffold repo: `pyproject.toml`, `Makefile`, `config.yaml` (AS_OF_DATE = 2026-10-21), `.gitignore`, ruff/sqlfluff config, pre-commit | Clean `make lint` |
| 1.2 | `ingest.py`: 20 sheets → bronze parquet (all strings + lineage cols) | `outputs/bronze/` |
| 1.3 | `standardise.py`: robust date parser, category maps, phone / e-mail / identifier cleaning, bounds, placeholder handling, BMI recompute; every change logged (SPEC §6a, FR0.x) | `outputs/silver/`, `change_log.csv` |
| 1.3b | `export_clean.py` + `docs/CLEANING.md`: cleaned workbook with real types, same row counts, `Cleaning_Summary` sheet | `data/clean/HCLS_cleaned.xlsx` |
| 1.4 | `dq/registry.yaml` + `dq/rules.py` + `runner.py` + `sql/dq/*.sql`: C01–C03 and the business rules of SPEC §3.2; generated missing-value, FK, format, date, domain and range rules for every table | rule engine (441 rules) |
| 1.5 | `scorecard.py`: `gold/dq_scorecard`, `dq_timeline`, `dq_history`; impact ranking | gold tables + `docs/01_dq_scorecard.md` (auto-generated) |
| 1.6 | Cross-check FK results against the `Referential_Integrity` sheet; explain any differences | section in scorecard doc |
| 1.7 | Build `tests/fixtures/mini_hcls.xlsx` (about 10 rows per table, one planted defect per rule) | fixture |
| 1.8 | Tests: unit (parser, mapper), data (each rule catches its defect), regression (C01 = 90, C02 = 123, C03 = 40) | green pytest |
| 1.9 | `ci.yml` stages 1–4 | PR checks run |
| 1.10 | **Finance Flash**: claims status breakdown (Approved $2.60M → paid $2.03M; pipeline $2.23M; denied $1.08M), certain vs estimated, one page | `docs/stakeholder_memos/00_finance_flash.md` |
| 1.11 | README v1 (how to run, status), DECISIONS D-001 (DuckDB vs Databricks), D-002 (as-of date), D-003 (the 90 nulls are unadjudicated claims, not corruption) | docs |

**Done when:** `make all` builds the scorecard and the cleaned workbook from scratch; all 3 confirmed issues are reproduced exactly; at least 40 additional rules are reported with counts, % and impact; the cleaned workbook has identical row counts and every format rule passes on it; CI stages 1–4 are green on the PR; Finance Flash exists.

### Sprint 2 — Phase 2: Diagnose root cause
**Branch:** `sprint-2-root-cause` · **Tag:** `v2.0` · **Spec:** FR2.x, §13 Q1–Q4

| # | Task | Output |
|---|---|---|
| 2.1 | `rootcause/timeline.py`: failures by year/quarter per Critical rule; test for a "break point" (structural change) vs flat | `gold/dq_timeline` charts |
| 2.2 | Hypothesis tree per Critical issue (app / API / DB / ETL), with diagnostic SQL in `sql/rootcause/` | evidence tables |
| 2.3 | Prove C01 is status-driven: null approved amounts by claim_status | evidence |
| 2.4 | Prove the broken joins: claims→billing patient mismatch (250/250), amount ratio (~65×), Rx-admin patient mismatch (400/400), with sample row pairs | evidence + D-004 "do not use claims→billing join" |
| 2.5 | Sentinel-ID analysis (0, −1, 88888, 999, 9999x) across tables | evidence |
| 2.6 | `lineage.py` + Mermaid lineage diagram | `docs/02_root_cause_report.md` |
| 2.7 | Interview guide (claims team, ETL owner) + ETL log checklist | appendix |
| 2.8 | Tests: evidence queries return expected shapes and counts; hypothesis verdicts reproducible | green pytest |

**Done when:** each Critical issue has a verdict (confirmed / likely / ruled out) backed by a query and numbers; Key Questions 1–4 are answered in draft.

### Sprint 3 — Phase 3: Finance reconciliation (Wednesday 5 PM)
**Branch:** `sprint-3-finance-recon` · **Tag:** `v3.0` · **Spec:** FR3.x, §13 Q6–Q7

| # | Task | Output |
|---|---|---|
| 3.1 | `sql/recon/claims_buckets.sql` + `recon/claims.py`: bucket classifier (Paid, Adjustment, Denied, Appeal, Pipeline, DQ Hold) with confidence | `gold/recon_claims` |
| 3.2 | Expected-value estimate for pipeline (historical approval ratio ≈ 77.8%), with a low/high range | summary rows |
| 3.3 | Tie-out: Σ buckets = $6,066,812.08; reconcile to the brief's $2.3M/$1.8M in a footnote | test + summary |
| 3.4 | `recon/excel_export.py`: `Claims Summary`, `Customer Detail`, `DQ Exceptions`, `Read Me`, formatted | `outputs/finance/*.xlsx` |
| 3.5 | Overcharge question: state "not determinable", give reasons, and list the data needed | finance brief section |
| 3.6 | `docs/03_finance_brief.md`: one page, plain language | brief |
| 3.7 | Tests: classifier unit tests, tie-out test, Excel sheet/column integration test, regression on gap = $578,766.32 | green pytest |
| 3.8 | Timing check: recon < 5 min (log duration) | audit log row |

**Done when:** Finance can say "We were paid $1.95M on $2.58M of approved claims (certain; $0.08M more is held for review). $2.23M is still being adjudicated; we expect about $1.17M of it (estimated, range $1.04M-$1.30M; $1.73M was the no-denial ceiling). $1.08M was denied." Every number traces to a claim row, and the workbook is produced only by code.

### Sprint 4 — Phase 4: Validate and plan remediation
**Branch:** `sprint-4-remediation` · **Tag:** `v4.0` · **Spec:** FR4.x, §11, §13 Q5 & Q8

| # | Task | Output |
|---|---|---|
| 4.1 | Remediation matrix: issue → action (backfill / quarantine / standardise / by-design) → owner, effort, risk, rollback | `docs/04_remediation_plan.md` |
| 4.2 | `backfill_sim.py`: C03 from Prescriptions; C02 match on patient + date ± 1 day; before/after counts, match confidence; runs on a copy only | sim report |
| 4.3 | `validators.py`: ingest-time NOT NULL / FK / range / date-order / enum checks, each mapped to the issue it prevents | module + tests |
| 4.4 | `databricks/jobs/`: `dq_daily.json` (02:00 UTC), `recon_weekly.json`, `audit_nightly.json` (retries, timeouts, notifications); notebooks call `hcls.cli` | job defs |
| 4.5 | Alerts: threshold (> 5% Critical), drift (> 10%), recon SLA (> 5 min) → `outputs/alerts.json` | monitoring |
| 4.6 | `deploy.yml` stages 5–6: `environment: production` gate, simulated Databricks deploy dry-run, release artefacts | full CI/CD |
| 4.7 | Senior DE sign-off checklist (staging evidence, rollback, approval) | plan appendix |
| 4.8 | Tests: validators reject planted bad rows; backfill sim is deterministic and never touches the source; job JSON schema check | green pytest |

**Status: delivered (v4.0).** **Done when:** all 6 CI/CD stages exist and run; a remediation and prevention plan exists for every Critical and High issue; backfill is shown on a copy with before/after counts.

### Sprint 5 — Phase 5: Audit-ready documentation
**Branch:** `sprint-5-audit-pack` · **Tag:** `v5.0` (final) · **Spec:** FR5.x, §12

| # | Task | Output |
|---|---|---|
| 5.1 | `audit/metrics.py` + `audit_log.py`: run-level audit trail, nightly metrics | `gold/audit_log`, `gold/audit_metrics` |
| 5.2 | Export Power BI-ready gold CSVs (no PII) | `outputs/gold/*.csv` |
| 5.3 | Power BI: 5 pages (Exec, Scorecard, Timeline, Finance, Patient Care & Compliance); `measures.dax.md`; theme | `powerbi/CloneStream_DQ.pbix` (built by Manas in Desktop from agent-written spec) |
| 5.4 | `docs/05_audit_pack.md`: all 8 Key Questions answered; scorecard; root causes; recon; remediation; prevention; monitoring | audit pack |
| 5.5 | Stakeholder memos: Finance, Compliance, Patient Care (one page each, plain language) | `docs/stakeholder_memos/` |
| 5.6 | Rubric self-assessment table mapping each criterion to evidence links | README section |
| 5.7 | Final README: architecture diagram, tool justification, how to run, CI badge, outputs index | README |
| 5.8 | Clean-clone test: fresh clone → `make all` → all outputs regenerate; CI green on `main` | release `v5.0` |

**Status: delivered (v5.0).** **Done when:** an auditor reading only `README.md` and `docs/05_audit_pack.md` can see scope, cause, money, fix and prevention, and every claim links to a reproducible output.

---

## 5. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Brief's $ figures don't match the data | Already true | High (credibility) | Report the data's figures and reconcile to the brief explicitly (D-003, S3.3) |
| Someone uses the claims→billing join to "answer" overcharging | Medium | Very high (false audit claim) | D-004; a test asserts recon never joins Billing |
| Only a free Databricks workspace (serverless, restricted internet) | High | Medium | DuckDB in CI; one notebook runs the pipeline and saves Delta tables (D-041); job JSON kept as a versioned design (D-001) |
| Counts drift because "future date" uses today | Medium | Medium | Fixed AS_OF_DATE in config (D-002) |
| Agent edits outside folder / pushes | Low | High | Constraint in SPEC §14 and in every sprint prompt; Manas reviews the diff before each commit |
| Power BI can't be built by the agent | Certain | Medium | Agent produces gold CSVs, measures and a page-by-page build spec; Manas builds the .pbix |
| Time overrun before Wed 5 PM | Medium | High | Finance Flash in S1 is the fallback; cut breadth, not correctness |

## 6. Decision log seeds (`DECISIONS.md`)

| ID | Decision | Why |
|---|---|---|
| D-001 | DuckDB locally and in CI; Databricks job definitions versioned, not live | No workspace; same SQL ports across |
| D-002 | `AS_OF_DATE = 2026-10-21` in config | Deterministic counts and tests |
| D-003 | The 90 null `approved_amount` values are classified as pipeline (estimated), not data loss | 100% are in non-final statuses |
| D-004 | Reconciliation uses Insurance_Claims only; the overcharging question is "not determinable yet" | Claims→Billing link mismatched on 250/250 rows |
| D-005 | Silver never drops rows; it flags instead | Auditability; nothing hidden |
| D-006 | Brief conflict: Phase 3 says "daily export", schedule says "weekly recon". Chosen: daily refresh of the export plus a weekly signed snapshot | Satisfies both |

## 7. Definition of Done (every sprint)

- [ ] All tasks in the sprint table are complete, or the cut is logged in `DECISIONS.md`
- [ ] `make all` and `pytest` pass locally; CI green on the PR
- [ ] Small, meaningful commits (not one big dump)
- [ ] `README.md` status table, `CHANGELOG.md` and `DECISIONS.md` updated
- [ ] No files touched outside the Capstone 3 folder; `Resources/` unchanged
- [ ] PR description lists what changed, evidence and the rubric dimension served
- [ ] Merged to `main` and tagged `vN.0`
