"""Simulated Databricks deploy (CI stage 6, task 4.6). Validates the job definitions and prints what a real deploy would run.

Nothing is sent anywhere: there is no workspace in this project (DECISIONS D-001). Writes outputs/deploy_plan.json.
Run:  python -m hcls.deploy.dry_run
"""

from __future__ import annotations

import json
import sys

from hcls import config
from hcls.deploy import validate_jobs


def plan() -> dict:
    problems = {k: v for k, v in validate_jobs.check_all().items() if v}
    if problems:
        raise ValueError(f"job definitions are invalid: {problems}")
    jobs = validate_jobs.load_jobs()
    items = []
    for key, job in jobs.items():
        items.append(
            {
                "job": job["name"],
                "file": f"databricks/jobs/{key}.json",
                "schedule_utc": job["schedule"]["quartz_cron_expression"],
                "tasks": [t["task_key"] for t in job["tasks"]],
                "command": f"databricks jobs create --json @databricks/jobs/{key}.json",
                "executed": False,
            }
        )
    return {"mode": "dry-run", "as_of_date": config.as_of_date().isoformat(), "jobs": items}


def main() -> int:
    try:
        result = plan()
    except ValueError as e:
        print(f"dry-run failed: {e}")
        return 1
    path = config.outputs_dir() / "deploy_plan.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for j in result["jobs"]:
        print(
            f"[dry-run] would run: {j['command']}   ({j['job']}, {j['schedule_utc']}, tasks: {' > '.join(j['tasks'])})"
        )
    print(f"[dry-run] {len(result['jobs'])} jobs validated, nothing deployed -> {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
