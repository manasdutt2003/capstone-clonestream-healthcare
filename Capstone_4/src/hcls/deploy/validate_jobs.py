"""Check the Databricks job definitions (CI stage 1, task 4.4): schema, notebooks, steps, retries, alerts, SLA.

Run:  python -m hcls.deploy.validate_jobs      (exit code 1 if any problem is found)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

from hcls import config


def jobs_dir() -> Path:
    return config.project_root() / "databricks" / "jobs"


def load_jobs(directory: Path | None = None) -> dict[str, dict]:
    d = directory or jobs_dir()
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(d.glob("*.json"))
        if p.name != "job.schema.json"
    }


def load_schema(directory: Path | None = None) -> dict:
    return json.loads(((directory or jobs_dir()) / "job.schema.json").read_text(encoding="utf-8"))


def check_job(job: dict, schema: dict, notebooks: Path | None = None) -> list[str]:
    from hcls.cli import COMMANDS

    problems: list[str] = []
    for err in jsonschema.Draft202012Validator(schema).iter_errors(job):
        problems.append(f"schema: {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}")
    nb_dir = notebooks or (config.project_root() / "databricks" / "notebooks")
    keys = {t.get("task_key") for t in job.get("tasks", [])}
    for t in job.get("tasks", []):
        step = t.get("notebook_task", {}).get("base_parameters", {}).get("step")
        if step is not None and step != "all" and step not in COMMANDS:
            problems.append(f"task {t.get('task_key')}: step '{step}' is not a command of python -m hcls")
        nb = Path(t.get("notebook_task", {}).get("notebook_path", "")).name
        if nb and not (nb_dir / f"{nb}.py").exists():
            problems.append(f"task {t.get('task_key')}: notebook '{nb}' not found in databricks/notebooks")
        for dep in t.get("depends_on", []):
            if dep["task_key"] not in keys:
                problems.append(f"task {t.get('task_key')}: depends on unknown task '{dep['task_key']}'")
        if t.get("timeout_seconds", 0) > job.get("timeout_seconds", 0):
            problems.append(f"task {t.get('task_key')}: timeout is longer than the whole job")
    if not job.get("webhook_notifications", {}).get("on_failure"):
        problems.append(
            "no Slack webhook_notifications.on_failure (failures must reach Slack as well as e-mail)"
        )
    if sum(1 for _ in job.get("tasks", [])) != len(keys):
        problems.append("duplicate task_key")
    return problems


def check_recon_sla(jobs: dict[str, dict]) -> list[str]:
    sla = float(config.load_config()["alerts"]["recon_sla_seconds"])
    rules = jobs.get("recon_weekly", {}).get("health", {}).get("rules", [])
    ok = any(r["metric"] == "RUN_DURATION_SECONDS" and r["value"] <= sla for r in rules)
    return [] if ok else [f"recon_weekly: no duration alert at or below the {sla:g}s SLA"]


def check_all() -> dict[str, list[str]]:
    jobs, schema = load_jobs(), load_schema()
    result = {name: check_job(job, schema) for name, job in jobs.items()}
    required = {"dq_daily", "recon_weekly", "audit_nightly"}
    for missing in sorted(required - set(jobs)):
        result[missing] = ["job definition missing"]
    result.setdefault("recon_weekly", []).extend(check_recon_sla(jobs))
    return result


def main() -> int:
    result = check_all()
    bad = {k: v for k, v in result.items() if v}
    for name in sorted(result):
        print(f"{'FAIL' if result[name] else 'ok  '} {name}")
        for p in result[name]:
            print(f"     - {p}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
