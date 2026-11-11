# Databricks notebook source
# One notebook runs one pipeline step, chosen by the task parameter `step`.
# It only calls the same command line the project uses locally (python -m hcls <step>), so there is no logic to maintain here.
# Slack: if the secret scope clonestream/slack_webhook exists it becomes SLACK_WEBHOOK_URL, and a failed step posts to Slack.

# COMMAND ----------

# MAGIC %pip install -e /Workspace/Repos/clonestream/capstone3

# COMMAND ----------

import os  # noqa: E402  (notebook cell order)

dbutils.widgets.text("step", "dq")  # noqa: F821  (dbutils is provided by Databricks)
step = dbutils.widgets.get("step")  # noqa: F821

try:  # the webhook URL is a secret: it lives in a Databricks secret scope, never in the repo
    os.environ.setdefault("SLACK_WEBHOOK_URL", dbutils.secrets.get("clonestream", "slack_webhook"))  # noqa: F821
except Exception:  # noqa: BLE001  (no scope configured: notifications fall back to a dry run)
    pass

# COMMAND ----------

from hcls import cli  # noqa: E402  (notebook cell order)
from hcls.monitoring import notify  # noqa: E402

try:
    code = cli.main([step])
except BaseException as exc:
    notify.notify_job(f"databricks:{step}", "failed", f"{type(exc).__name__} in step `{step}`")
    raise
if code != 0:
    notify.notify_job(f"databricks:{step}", "failed", f"exit code {code} in step `{step}`")
    raise RuntimeError(f"hcls {step} failed with exit code {code}")
