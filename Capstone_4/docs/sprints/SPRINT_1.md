# Sprint 1 - Understand the scope (+ data cleaning)

**Branch:** `sprint-1-dq-scope` | **Tag:** `v1.0` | **Serves rubric:** 1 (discovery), 2 (tools), 3 (tests/CI), 4 (Finance Flash)

## What this sprint delivers
Scaffold, ingest, **cleaned workbook**, 441-rule data-quality engine, scorecard + timeline, Finance Flash, 176 tests, CI stages 1-4.
Plan tasks 1.1 - 1.11 (plus 1.3b, the cleaned workbook).

## One-time setup (first sprint only)
```bash
cd "C:\Users\manas.dutt\Desktop\GGTP_BLR_DP_SEP_26\Projects\Individual\Manas Dutt\Week 4\Capstone 3"
# unzip capstone3_sprint_1.zip here (overwrite if asked)
git init -b main
git add README.md SPEC.md PLAN.md DECISIONS.md .gitignore Resources
git commit -m "docs: add project spec, plan, decision log and input files"
git remote add origin <your-repo-url>
git push -u origin main
```
In GitHub: **Settings -> Environments -> New environment `production`** and add yourself as a required reviewer (used in Sprint 4). **Settings -> Branches** -> protect `main` (require a pull request and passing checks).

## Run it locally first
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
make all && make test && make lint          # or the python -m / pytest / ruff commands in README
```
Expected: `176 passed`, lint clean, `docs/01_dq_scorecard.md` regenerated with the same numbers.

## Commit on the sprint branch (small, meaningful commits)
```bash
git switch -c sprint-1-dq-scope

git add pyproject.toml Makefile .sqlfluff .pre-commit-config.yaml config.yaml src/hcls/__init__.py src/hcls/__main__.py src/hcls/config.py
git commit -m "chore: scaffold project with fixed as-of date, tooling and config"

git add src/hcls/ingest.py
git commit -m "feat(ingest): read 20 sheets as text into bronze without NA conversion"

git add src/hcls/standardise.py src/hcls/export_clean.py data/clean docs/CLEANING.md
git commit -m "feat(clean): standardise dates, categories, contacts and impossible values; export cleaned workbook"

git add src/hcls/dq sql/dq
git commit -m "feat(dq): add 441-rule engine with business rules, FK, format, domain and range checks"

git add src/hcls/reports.py src/hcls/cli.py docs/01_dq_scorecard.md
git commit -m "feat(report): generate scorecard, timeline, RI cross-check and CLI"

git add src/hcls/recon sql/recon docs/stakeholder_memos
git commit -m "feat(recon): add Finance Flash with certain vs estimated labels"

git add tests
git commit -m "test: add unit, data-validation, regression and integration suites"

git add .github
git commit -m "ci: add stages 1-4 (quality, unit, data, integration with coverage gate)"

git add -A
git commit -m "docs: update README, CHANGELOG, DECISIONS, SPEC v1.1 and PLAN v1.1 for sprint 1"

git push -u origin sprint-1-dq-scope
```
(If `git add -A` picks up nothing new, skip that last commit.)

## Pull request
**Title:** `Sprint 1: data-quality scope, cleaned workbook and Finance Flash`

**Body:**
```
## What changed
- Ingest + cleaning pipeline; cleaned workbook with identical row counts
- 441-rule DQ engine; scorecard, timeline, RI cross-check
- Finance Flash (preliminary, certain vs estimated)
- 176 tests, 97% coverage, CI stages 1-4

## Evidence
- C01 = 90/250, C02 = 123/400, C03 = 40/206 reproduced exactly
- 164 further rules report findings (docs/01_dq_scorecard.md)
- Cleaning fixes all 85 format/placeholder/domain/range rules; C01-C03, A02, A30 unchanged

## Rubric
Dimension 1, 2, 3, 4
```
Wait for the 4 CI stages to go green, then merge.

## After merge
```bash
git switch main && git pull
git tag -a v1.0 -m "Sprint 1: understand the scope" && git push --tags
```

## Definition of done - checked
- [x] `make all` builds scorecard and cleaned workbook from scratch
- [x] 3 confirmed issues reproduced exactly
- [x] 40+ additional issues with counts, % and impact
- [x] Cleaned workbook: same row counts, every format rule passes
- [x] Finance Flash exists
- [x] README, CHANGELOG, DECISIONS updated
- [ ] CI green on the PR (you confirm after pushing)
