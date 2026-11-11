# Databricks

## Run on Databricks Free Edition (done, D-041)

| Notebook | What it does |
|---|---|
| `notebooks/00_setup.py` | Creates schema `workspace.clonestream` and volume `raw` |
| `notebooks/01_run_pipeline.py` | Unzips the project zip from `/Volumes/workspace/clonestream/raw`, runs `python -m hcls all`, saves outputs as 78 Delta tables, prints a check |

Upload the project zip to the volume, then run `00_setup`, then `01_run_pipeline` (or create a job with task `Run_Pipeline` that runs it, schedule 02:00 AM). Expected check: 20 sheets, 10,203 rows, 0 rows dropped, 164 findings, 5 Critical.

Limits of the free edition: serverless only, restricted internet (so Slack runs as a dry run), and the compute is still DuckDB and pandas on one machine. Delta tables hold the results.

# Jobs API definitions (design, not deployed)

The job definitions below were not deployed (DECISIONS D-001, D-031): the free workspace cannot use them. They are **definitions**, checked by tests and dry-run by the pipeline. Nothing in this folder's JSON talks to Databricks.

| Job file | Schedule (UTC) | Steps | Limits |
|---|---|---|---|
| `jobs/dq_daily.json` | daily 02:00 | ingest, clean, dq, alerts, notify | 30 min job, 15 min per task |
| `jobs/recon_weekly.json` | Mondays 06:00 | ingest, clean, recon | 10 min job; **duration alert at 5 min (SLA)** |
| `jobs/audit_nightly.json` | daily 03:00 | all, alerts | 45 min job |

Every task retries twice (60 s apart), times out, and the job emails `data-engineering@clonestream.example` on failure. Each job also has a `webhook_notifications.on_failure` entry; replace its id (`REPLACE-WITH-SLACK-DESTINATION-ID`) with a Databricks notification destination that points at your Slack webhook. `dq_daily` ends with a `notify` task, and the notebook posts a failed step to Slack itself using the secret `clonestream/slack_webhook`. Replace the e-mail address too, before real use. Setup: [docs/NOTIFICATIONS.md](../docs/NOTIFICATIONS.md).

`notebooks/run_step.py` is the single notebook every task calls; its `step` parameter is a command of `python -m hcls`.

Check the definitions: `python -m hcls.deploy.validate_jobs`. Simulate the deploy: `python -m hcls.deploy.dry_run` (writes `outputs/deploy_plan.json`).
To deploy for real, someone with workspace access runs the printed `databricks jobs create --json @...` commands after the approval gate.
