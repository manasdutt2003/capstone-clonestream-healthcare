# Slack notifications

The pipeline posts to Slack when something needs attention. Everything is code (`src/hcls/monitoring/notify.py`), tested, and off by default until you give it a webhook.

## What is sent

| Message | When | Example |
|---|---|---|
| **Alerts** | After `python -m hcls alerts`, if the alert set is new or changed | "CloneStream data quality: 5 alerts" with one line per alert (rule id, stakeholder, what failed, the limit) |
| **All clear** | Once, when the alerts go away | "all clear, no alerts in the latest run" |
| **Job failed / succeeded** | A failed Databricks step; the end of the GitHub deploy | "CloneStream job capstone3-deploy: FAILED" with a link to the run |

Messages contain rule ids, counts and table names only: **no patient data and no amounts per person.** The webhook URL is never printed, logged or written to a file.

Behaviour you can rely on:

- **No webhook set = dry run.** The message is written to `outputs/slack_preview.json` and nothing is sent. This is what happens in tests, in CI without the secret, and on a fresh clone.
- **Slack down or webhook wrong = the pipeline still passes.** The send is retried (up to 3 times), then a line is printed. Add `--strict` if you want it to exit 1 instead.
- **Same alerts as the last run = not sent again.** A daily job would otherwise post the same five alerts every morning. `--force` sends anyway. A failed send is not remembered, so it is retried on the next run.
- **Only Slack URLs are accepted** (`https://hooks.slack.com/...`), so a typo or a bad config cannot send the message somewhere else.

## Set it up (about 5 minutes)

1. Go to <https://api.slack.com/apps> > **Create New App** > **From scratch**, name it "CloneStream DQ", pick your workspace.
2. **Incoming Webhooks** > turn it on > **Add New Webhook to Workspace** > choose the channel (for example `#data-quality`) > copy the URL. Treat it like a password.
3. Use it:
   - **On your computer (PowerShell):** `$env:SLACK_WEBHOOK_URL = "<the url>"` then `python -m hcls notify --force`
   - **In GitHub:** repo **Settings > Secrets and variables > Actions > New repository secret**, name `SLACK_WEBHOOK_URL`. The deploy workflow passes it automatically.
   - **In Databricks:** create the secret `clonestream/slack_webhook` (`databricks secrets put-secret clonestream slack_webhook`). The notebook picks it up. For the Databricks failure hook, create a notification destination of type Slack and put its id in each job's `webhook_notifications.on_failure` (replace `REPLACE-WITH-SLACK-DESTINATION-ID`).
4. **Send one test message first:** `python -m hcls notify --job test --status ok --detail "hello from CloneStream"`. If it does not arrive, see "Troubleshooting".

## Send different stakeholders to different channels

Create one webhook per channel and set any of these; an alert for a group goes to its own webhook, everything else to `SLACK_WEBHOOK_URL`:

| Variable | Receives |
|---|---|
| `SLACK_WEBHOOK_URL` | Default, and the job messages |
| `SLACK_WEBHOOK_URL_FINANCE` | Alerts whose owner is Finance (for example C01, A02) |
| `SLACK_WEBHOOK_URL_COMPLIANCE` | Compliance (for example C02) |
| `SLACK_WEBHOOK_URL_PATIENTCARE` | Patient Care (for example C03, A30) |
| `SLACK_WEBHOOK_URL_OPS` | Ops |

## Commands

```bash
python -m hcls notify                      # alerts from outputs/alerts.json (part of `python -m hcls all`)
python -m hcls notify --dry-run            # build the message, send nothing
python -m hcls notify --force              # send even if unchanged
python -m hcls notify --strict             # exit 1 if delivery fails
python -m hcls notify --job NAME --status failed --detail "what happened"
```

Settings are in `config.yaml` under `notifications.slack` (`enabled`, `only_on_change`, `notify_when_clear`, `max_alerts_listed`, `timeout_seconds`, `retries`).

## Where it runs

| Where | What triggers it |
|---|---|
| Your computer / any shell | `python -m hcls all` (the `notify` step comes right after `alerts`), or `python -m hcls notify` |
| GitHub Actions deploy | The rebuild step gets the secret; a success or failure message is posted at the end |
| Databricks (design) | `dq_daily` ends with a `notify` task (02:00 UTC); a failed step posts from the notebook; `webhook_notifications.on_failure` covers job-level failures |

## Troubleshooting

| You see | Meaning |
|---|---|
| `notify: dry-run ... (no webhook set ...)` | `SLACK_WEBHOOK_URL` is not set in that shell or secret store |
| `notify: unchanged` | Nothing new since the last send; use `--force` to test |
| `failed (HTTP 404)` or `HTTP 403` | The webhook was revoked or mistyped; create a new one |
| `webhook is not a Slack URL` | The value must start with `https://hooks.slack.com/` |
| `failed (gave up after 3 attempts: network error)` | No route to Slack from that machine (proxy or firewall) |

## Limits to know

- This was tested with simulated Slack responses and a local stand-in server, **not** against a real workspace. Send the test message above before relying on it.
- An incoming webhook posts to one channel and cannot reply in threads or edit messages. A Slack bot token would allow that; it needs an app install, so it is left as a future step (D-040).
- The Databricks job JSON is a design (D-001). On the Free Edition run (D-041) outbound internet is restricted, so `notify` is a dry run there.
