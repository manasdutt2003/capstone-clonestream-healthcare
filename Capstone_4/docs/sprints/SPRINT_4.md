# Sprint 4 - Validate and plan remediation

**Branch:** `sprint-4-remediation` | **Tag:** `v4.0` | **Serves rubric:** 3 (git, tests, CI/CD), 2, 1, 5

## What this sprint delivers
Backfill simulation on a copy (recovers 0 of 40 and 0 of 123), 49 ingest validators, alerts, three Databricks job definitions (design only), `deploy.yml` stages 5-6 with an approval gate, and `docs/04_remediation_plan.md`. Plan tasks 4.1 - 4.8.

## 1. Merge Sprint 3 first
Merge the Sprint 3 pull request, then tag `v3.0` if you have not.

## 2. Put the files in place
Extract `Capstone 3.zip` **over** your existing folder:

`C:\Users\manas.dutt\Downloads\GGTP_CHN_DP_SEP_26\Projects\Individual\Manas Dutt\Week 4\Capstone 3`

## 3. Sync with main, then branch
```bash
cd "C:\Users\manas.dutt\Downloads\GGTP_CHN_DP_SEP_26"
git switch main
git pull origin main
git switch -c sprint-4-remediation
```
If you extracted the zip before switching, run `git stash push -u` first and `git stash pop` after.

## 4. Run it locally
```bash
cd "Projects\Individual\Manas Dutt\Week 4\Capstone 3"
.venv\Scripts\activate
pip install -e ".[dev]"
make all && make test && make lint
python -m hcls.deploy.validate_jobs
python -m hcls.deploy.dry_run
```
Without `make`: `python -m hcls all`, `pytest`, `ruff check .`, `ruff format --check .`, `sqlfluff lint sql --dialect duckdb`.

## 5. Commit in groups (name files; do not use `git add -A`, the CRLF noise would sweep in other students' files)
```bash
cd "Projects\Individual\Manas Dutt\Week 4\Capstone 3"

git add src/hcls/remediation/__init__.py src/hcls/remediation/common.py src/hcls/remediation/backfill_sim.py
git commit -m "feat(remediation): simulate C03/C02 backfill on a copy with confidence labels"

git add src/hcls/remediation/validators.py
git commit -m "feat(remediation): add 49 ingest validators and catch report"

git add src/hcls/remediation/plan.py docs/04_remediation_plan.md
git commit -m "feat(remediation): generate remediation plan covering all Critical/High rules"

git add src/hcls/monitoring
git commit -m "feat(monitoring): threshold, drift and recon-SLA alerts"

git add databricks src/hcls/deploy
git commit -m "feat(deploy): Databricks job definitions, schema, validator and dry-run"

git add .github/workflows/ci.yml .github/workflows/deploy.yml ci config.yaml
git commit -m "ci: add deploy stages 5-6 with production approval gate and root workflow copies"

git add src/hcls/cli.py Makefile tests
git commit -m "feat(cli): backfill, validate, alerts commands; tests"

git add README.md SPEC.md PLAN.md DECISIONS.md CHANGELOG.md docs/sprints/SPRINT_4.md
git commit -m "docs: sprint 4 (D-027..D-034, SPEC v1.4, PLAN v1.4)"

git push -u origin sprint-4-remediation
```
Check with `git status` that nothing from `Capstone 3` is left uncommitted.

## 6. GitHub setup (manual, one time)
1. Settings -> Environments -> New environment `production` -> tick **Required reviewers** and add yourself.
2. GitHub only runs workflows from the repo root. Copy `ci/root-workflows/manas-capstone3-ci.yml` and `manas-capstone3-deploy.yml` into the repo's root `.github/workflows/`. They only trigger on changes under your folder.
3. The class repo's failing "requirements.txt" workflow is someone else's workflow and is unrelated.

## 7. Pull request
```
## What changed
- Backfill simulation on a copy: C03 0 of 40, C02 0 of 123 recoverable safely
- 49 ingest validators (would reject 1,903 rows), alerts (5 threshold alerts)
- Databricks jobs (design only), deploy stages 5-6 with production approval gate
- docs/04_remediation_plan.md for all 28 Critical/High rules

## Evidence
- make all, tests and lint green; source fingerprint unchanged after simulation
```
Then, after merge: `git switch main && git pull origin main && git tag -a v4.0 -m "Sprint 4: validate and plan remediation" && git push origin v4.0`
