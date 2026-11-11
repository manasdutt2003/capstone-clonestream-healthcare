# Sprint 3 - Finance reconciliation

**Branch:** `sprint-3-finance-recon` | **Tag:** `v3.0` | **Serves rubric:** 4 (business logic and communication), 1, 3, 5

## What this sprint delivers
`python -m hcls recon` builds the finance workbook and `docs/03_finance_brief.md`. Every claim is in exactly one bucket and the buckets tie to the cent ($6,066,812.08). Plan tasks 3.1 - 3.8. 37 new tests (260 total).

## 1. Merge Sprint 2 first
Sprint 3 builds on Sprint 2. Merge the Sprint 2 pull request on GitHub (and tag `v2.0` if you want), otherwise this branch carries Sprint 2 files too.

## 2. Put the files in place
Extract `Capstone 3.zip` **over** your existing folder (it is a full snapshot, so changed files are overwritten):

`C:\Users\manas.dutt\Downloads\GGTP_CHN_DP_SEP_26\Projects\Individual\Manas Dutt\Week 4\Capstone 3`

## 3. Sync with main, then branch
```bash
cd "C:\Users\manas.dutt\Downloads\GGTP_CHN_DP_SEP_26"
git status
git stash push -u -m "sprint-3 files"
git switch main
git fetch origin
git pull origin main
git switch -c sprint-3-finance-recon
git stash pop
```

## 4. Run it locally
```bash
cd "Projects\Individual\Manas Dutt\Week 4\Capstone 3"
.venv\Scripts\activate
pip install -e ".[dev]"
make all && make test && make lint
```
Expected: `260 passed`, lint clean, and `outputs/finance/CloneStream_Claims_Reconciliation_2026-10-21.xlsx` created (about 1 second for the reconciliation step). Without `make`: `python -m hcls all`, `pytest`, `ruff check src tests`, `ruff format --check src tests`, `sqlfluff lint sql --dialect duckdb`.

The workbook lives in `outputs/` (not committed, like every generated output). Send Finance the file, or regenerate it with `python -m hcls recon`.

## 5. Commit in groups
```bash
cd "Projects\Individual\Manas Dutt\Week 4\Capstone 3"

git add sql/recon/claims_buckets.sql src/hcls/recon/claims.py
git commit -m "feat(recon): classify claims into buckets with holds, tie-out and expected value"

git add src/hcls/recon/excel_export.py
git commit -m "feat(recon): write finance workbook (summary, customer detail, exceptions, read me)"

git add src/hcls/recon/brief.py src/hcls/recon/flash.py docs/03_finance_brief.md docs/stakeholder_memos
git commit -m "feat(recon): add finance brief and label the flash pipeline figure as a ceiling"

git add src/hcls/cli.py Makefile
git commit -m "feat(cli): add recon command with tie-out stop and SLA timing log"

git add tests
git commit -m "test(recon): cover buckets, holds, tie-out, expected value, workbook and pinned numbers"

git add -A
git commit -m "docs: update README, CHANGELOG, DECISIONS (D-021..D-026), SPEC v1.3, PLAN v1.3 for sprint 3"

git push -u origin sprint-3-finance-recon
```
Run `git status` before the last `git add -A`; if it lists files outside `Capstone 3`, use `git add .` from inside the folder instead.

## 6. Pull request
```bash
gh pr create --base main --head sprint-3-finance-recon --title "Sprint 3: finance reconciliation (buckets, workbook, brief)" --body "See docs/sprints/SPRINT_3.md section 6"
```
Better: paste this as the PR description on GitHub.
```
## What changed
- hcls recon: claim buckets (Paid, Adjustment, Denied, Under appeal, Pipeline, DQ Hold) with confidence
- Excel workbook: Claims Summary, Customer Detail, DQ Exceptions, Read Me
- docs/03_finance_brief.md (plain language, over-charging answer, data needed)
- 37 new tests (260 total), 98% coverage

## Evidence
- Buckets tie to $6,066,812.08 across 250 claims
- Certain: Paid $1,945,489; estimated pipeline $2.23M (expected $1.17M, range $1.04M-$1.30M)
- Correction to the Finance Flash: the $1.73M pipeline figure ignored denials; it is the ceiling
- Over-charging not determinable (claim -> bill link wrong on 250 of 250)

## Rubric
Dimension 4 (primary), 1, 3, 5
```
Wait for CI, then merge.

## 7. After merge
```bash
git switch main && git pull origin main
git tag -a v3.0 -m "Sprint 3: finance reconciliation" && git push origin v3.0
```

## What to read first
`docs/03_finance_brief.md`, then open the workbook's `Claims Summary` sheet.

## Decisions to be aware of
D-021 (when a claim is held), D-022 (expected value includes denials), D-023 (the paid figure is lower than the Flash), D-025 (the brief's numbers cannot be reproduced).
