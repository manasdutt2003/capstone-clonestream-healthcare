# Sprint 2 - Diagnose root cause

**Branch:** `sprint-2-root-cause` | **Tag:** `v2.0` | **Serves rubric:** 1 (discovery and root cause), 3 (tests), 5 (judgement: refusing to over-claim)

## What this sprint delivers
`python -m hcls rootcause` and the report `docs/02_root_cause_report.md`: timeline test, link health, lineage map, 14 hypotheses with computed verdicts, placeholder-id analysis, interview guide, ETL checklist. Plan tasks 2.1 - 2.8. 47 new tests (223 total).

## 1. Put the files in place
The zip is named **Capstone 3** and holds a full snapshot of the project. Extract it **over** your existing folder so changed files are overwritten and nothing else is touched:

`C:\Users\manas.dutt\Downloads\GGTP_CHN_DP_SEP_26\Projects\Individual\Manas Dutt\Week 4\Capstone 3`

Do not delete your `.git` folder (if the project folder is inside the shared class repo, `.git` is at the repo root, which is fine).

## 2. Sync with main first
```bash
cd "C:\Users\manas.dutt\Downloads\GGTP_CHN_DP_SEP_26"
git status
git stash push -u -m "sprint-2 files"      # only if status shows changes you want to park
git switch main
git fetch origin
git pull origin main
git switch -c sprint-2-root-cause
git stash pop                              # only if you stashed
```
If Sprint 1 is not merged yet, merge its PR first, then pull main again, otherwise this branch will carry Sprint 1 files as well.

## 3. Run it locally
```bash
cd "Projects\Individual\Manas Dutt\Week 4\Capstone 3"
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
make all && make test && make lint
```
Expected: `223 passed`, lint clean, `docs/02_root_cause_report.md` regenerated with `14 hypotheses {'Ruled out': 5, 'Confirmed': 3, 'Likely': 2, ...}`. Without `make`: `python -m hcls all`, `pytest`, `ruff check src tests`, `ruff format --check src tests`, `sqlfluff lint sql --dialect duckdb`.

## 4. Commit in groups
```bash
git add sql/rootcause src/hcls/rootcause/timeline.py
git commit -m "feat(rootcause): add yearly and quarterly failure timeline with chi-square change test"

git add src/hcls/rootcause/evidence.py src/hcls/rootcause/__init__.py
git commit -m "feat(rootcause): add evidence queries and computed hypothesis verdicts"

git add src/hcls/rootcause/lineage.py
git commit -m "feat(rootcause): rate foreign-key links by patient match and draw lineage map"

git add src/hcls/reports.py src/hcls/cli.py Makefile docs/02_root_cause_report.md
git commit -m "feat(report): add rootcause command and root-cause report with interview guide"

git add tests
git commit -m "test(rootcause): cover timeline, lineage, evidence SQL, verdict logic and pinned conclusions"

git add -A
git commit -m "docs: update README, CHANGELOG, DECISIONS (D-015..D-020), SPEC v1.2, PLAN v1.2 for sprint 2"

git push -u origin sprint-2-root-cause
```

## 5. Pull request
```bash
gh pr create --base main --head sprint-2-root-cause --title "Sprint 2: root-cause diagnosis (timeline, link health, hypotheses)" --body "See docs/sprints/SPRINT_2.md section 5"
```
Better: paste this text as the PR description on GitHub (it needs more than the one-line body above):
```
## What changed
- `hcls rootcause` command and docs/02_root_cause_report.md
- Timeline test (chi-square) for C01, C02, C03, A02, A30
- Link health for 6 foreign-key links; lineage map of 39 links
- 14 hypotheses with computed verdicts; interview guide; ETL checklist
- 47 new tests (223 total), 98% coverage

## Evidence
- C01: all 90 blanks are open claims (status-driven), flat across 7 years (p = 0.96)
- C02: flat across 7 years (p = 0.50); only 1 of 277 linked visits names the same patient
- Claim -> bill link matches the right patient 0 of 250 times, so over-charging cannot be determined
- Only Billing -> Appointments is sound (248 of 249)

## Rubric
Dimension 1, 3, 5
```
Wait for the 4 CI stages to go green, then merge.

## 6. After merge
```bash
git switch main && git pull origin main
git tag -a v2.0 -m "Sprint 2: diagnose root cause" && git push origin v2.0
```

## Heads up: where CI runs
GitHub only runs workflows from `.github/workflows` at the **repository root**. If `Capstone 3` is a subfolder of the shared class repo, the Sprint 1 workflow will not trigger. Tell me the repo layout before Sprint 4 (deploy and approval gate) and I will adapt the workflow paths.

## What you should read first
Section 1 of `docs/02_root_cause_report.md` (plain-language answer per issue), then section 4 (link health and map).
