# CloneStream Healthcare — Data Crisis, Reconciliation and Audit Pack

A hospital network found data-integrity problems across claims, visits and medical records,
with an unexplained revenue gap, a **Finance deadline on Wednesday 5 PM** and **auditors on-site
Friday**. This repository finds out what is broken, cleans the data, reconciles the money, plans
the fix and packages the evidence — all as code, versioned, tested and rebuilt with one command.

> Week 4 individual capstone · Perficient Global AI First Academy · Author: **Manas Dutt**

## Headline

| | |
|---|---|
| Claim dollars reconciled | **$6,066,812.08 — to the cent** |
| Paid (certain) | **$1,945,489** on 97 approved claims |
| Expected recovery | $1.17M (range $1.04M–$1.30M) |
| Data-quality rules run | **441** → 164 findings (5 Critical, 23 High, 73 Medium, 63 Low) |
| Tests | **349** |
| Full rebuild | **~18 seconds**, one command |

## Delivered in five sprints

| Sprint | Phase | Tag |
|---|---|---|
| 1 | Understand the scope (+ data cleaning) | `v1.0` |
| 2 | Diagnose root cause | `v2.0` |
| 3 | Finance reconciliation | `v3.0` |
| 4 | Validate and plan remediation | `v4.0` |
| 5 | Audit-ready documentation | `v5.0` |

## What the analysis found

**The three reported failures are real, and reproduce exactly:** 90/250 claims without an
approved amount (36%), 123/400 visits without an appointment (30.75%), 40/206 medical records
with no prescribed medication (19.4%).

**Every claim dollar sits in exactly one bucket** — paid $1.95M, adjustment $0.64M, denied
$1.12M, under appeal $0.16M, pipeline $2.23M. They tie to $6,066,812.08 exactly, and the build
fails if they don't.

**Certain and estimated figures are never blended.** The 90 undecided claims hold $2,225,289;
expected recovery is stated with a range, and the ceiling is stated separately.

**Over-charging is declared not determinable.** The claim→bill link points at the wrong patient
on **250 of 250** claims. A number built on that join would look precise and be wrong, so the
recommendation is to hold refund decisions until the link is repaired.

**It is a design gap, not a recent incident.** Failure rates are statistically flat across all
seven years (p = 0.96 and 0.50). 14 hypotheses were tested, with verdicts recorded.

**Backfill does not work.** Simulated on a copy: **0 of 40** medical records and **0 of 123**
visits can be filled safely. Fix at the source and review by hand.

## Audit readiness

49 ingest validators (they would reject 1,903 rows), every run logged with who/when/code
version/result, and a SHA-256 fingerprint of every output in `audit_outputs.csv` — `make verify`
fails if a single file was edited. Also ships Slack threshold alerts, a scheduled Databricks job,
a Power BI build guide, and memos for Finance, Compliance and Patient Care.

## Quick start

```bash
cd Capstone_4
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

make all     # ingest → clean → dq → flash → rootcause → recon → backfill →
             # validate → alerts → audit → powerbi → docs   (~18 seconds)
make test    # 349 tests
make lint    # ruff + sqlfluff
```

No `make` on Windows? Use `python -m hcls all`, `pytest`, `ruff check src tests`.

## Where to start reading

- **Auditors:** [`Capstone_4/docs/05_audit_pack.md`](Capstone_4/docs/05_audit_pack.md)
- **Finance:** [`Capstone_4/docs/03_finance_brief.md`](Capstone_4/docs/03_finance_brief.md)
- **Root cause:** [`Capstone_4/docs/02_root_cause_report.md`](Capstone_4/docs/02_root_cause_report.md)
- **Scorecard:** [`Capstone_4/docs/01_dq_scorecard.md`](Capstone_4/docs/01_dq_scorecard.md)
- **Presentation narrative:** [`README_presentation.md`](README_presentation.md)

> **Note:** the datasets here are course-provided synthetic data for a fictional healthcare
> scenario. No real patient or claims data is present.
