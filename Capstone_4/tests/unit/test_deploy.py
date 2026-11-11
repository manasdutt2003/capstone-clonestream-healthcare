"""Databricks job definitions, the simulated deploy, and the workflow files (CI stages 1, 5 and 6)."""

import copy
import json

import pytest
import yaml

from hcls import config
from hcls.deploy import dry_run, root_workflows, validate_jobs

ROOT = config.project_root()


@pytest.fixture
def jobs():
    return validate_jobs.load_jobs()


@pytest.fixture
def schema():
    return validate_jobs.load_schema()


def test_real_job_definitions_are_valid():
    result = validate_jobs.check_all()
    assert set(result) == {"dq_daily", "recon_weekly", "audit_nightly"}
    assert all(not v for v in result.values()), result


def test_schedules_match_the_spec(jobs):
    assert jobs["dq_daily"]["schedule"]["quartz_cron_expression"] == "0 0 2 * * ?"  # 02:00 UTC daily
    assert all(j["schedule"]["timezone_id"] == "UTC" for j in jobs.values())
    assert all(j["email_notifications"]["on_failure"] for j in jobs.values())
    assert all(j["webhook_notifications"]["on_failure"] for j in jobs.values())  # failures also reach Slack
    assert all(t["max_retries"] >= 1 and t["timeout_seconds"] > 0 for j in jobs.values() for t in j["tasks"])


def test_recon_has_a_five_minute_duration_alert(jobs):
    rules = jobs["recon_weekly"]["health"]["rules"]
    assert any(r["metric"] == "RUN_DURATION_SECONDS" and r["value"] <= 300 for r in rules)
    assert validate_jobs.check_recon_sla(jobs) == []
    broken = copy.deepcopy(jobs)
    broken["recon_weekly"]["health"]["rules"][0]["value"] = 900
    assert validate_jobs.check_recon_sla(broken)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda j: j["tasks"][0].pop("max_retries"), "max_retries"),
        (lambda j: j["email_notifications"].pop("on_failure"), "on_failure"),
        (lambda j: j.pop("webhook_notifications"), "Slack"),
        (
            lambda j: j["tasks"][0]["notebook_task"]["base_parameters"].update(step="not_a_command"),
            "not a command",
        ),
        (
            lambda j: j["tasks"][0]["notebook_task"].update(
                notebook_path="/Repos/x/databricks/notebooks/missing"
            ),
            "not found",
        ),
        (lambda j: j["tasks"][1].update(depends_on=[{"task_key": "ghost"}]), "unknown task"),
        (lambda j: j["tasks"][0].update(timeout_seconds=10**6), "longer than the whole job"),
        (lambda j: j["schedule"].update(timezone_id="Asia/Calcutta"), "timezone_id"),
        (lambda j: j.update(name="other-name"), "name"),
    ],
)
def test_bad_job_definitions_are_rejected(jobs, schema, mutate, expected):
    job = copy.deepcopy(jobs["dq_daily"])
    mutate(job)
    problems = validate_jobs.check_job(job, schema)
    assert any(expected in p for p in problems), problems


def test_dry_run_plans_every_job_and_deploys_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(config.load_config()["paths"], "outputs", str(tmp_path))
    assert dry_run.main() == 0
    plan = json.loads((tmp_path / "deploy_plan.json").read_text())
    assert plan["mode"] == "dry-run" and len(plan["jobs"]) == 3
    assert all(
        j["executed"] is False and j["command"].startswith("databricks jobs create") for j in plan["jobs"]
    )
    assert "nothing deployed" in capsys.readouterr().out


def test_dry_run_refuses_invalid_definitions(monkeypatch):
    monkeypatch.setattr(validate_jobs, "check_all", lambda: {"dq_daily": ["schema: broken"]})
    with pytest.raises(ValueError, match="invalid"):
        dry_run.plan()


def load_workflow(name):
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def test_ci_has_four_stages_and_checks_the_job_files():
    wf = load_workflow("ci.yml")
    assert list(wf["jobs"]) == [
        "stage-1-code-quality",
        "stage-2-unit-tests",
        "stage-3-data-tests",
        "stage-4-integration",
    ]
    stage1 = json.dumps(wf["jobs"]["stage-1-code-quality"])
    assert "hcls.deploy.validate_jobs" in stage1 and "sqlfluff" in stage1 and "ruff format --check" in stage1
    assert "--cov-fail-under=80" in json.dumps(wf["jobs"]["stage-4-integration"])


def test_deploy_has_the_approval_gate_and_a_simulated_deploy():
    wf = load_workflow("deploy.yml")
    gate, deploy = wf["jobs"]["stage-5-approval"], wf["jobs"]["stage-6-deploy"]
    assert (
        gate["environment"] == "production"
    )  # the required reviewer is configured on this environment in GitHub
    assert deploy["needs"] == "stage-5-approval"
    text = json.dumps(deploy)
    assert (
        "hcls.deploy.dry_run" in text and "gh release create" in text and "databricks jobs create" not in text
    )
    triggers = wf[True] if True in wf else wf["on"]  # PyYAML reads the key `on` as boolean True
    assert triggers["workflow_run"]["workflows"] == ["CI"] and triggers["workflow_run"]["branches"] == [
        "main"
    ]


def test_root_copies_are_in_sync_with_the_project_workflows():
    built = root_workflows.build()
    for name, text in built.items():
        on_disk = (ROOT / "ci" / "root-workflows" / name).read_text(encoding="utf-8")
        assert on_disk == text, f"{name} is stale: run python -m hcls.deploy.root_workflows"
    sub = config.load_config()["ci"]["repo_subpath"]
    ci = yaml.safe_load(built["manas-capstone3-ci.yml"])
    assert ci["defaults"]["run"]["working-directory"] == sub
    assert ci["name"] == root_workflows.NAME_CI
    triggers = ci[True] if True in ci else ci["on"]
    assert triggers["pull_request"]["paths"] == [f"{sub}/**"]
    dep = yaml.safe_load(built["manas-capstone3-deploy.yml"])
    dep_triggers = dep[True] if True in dep else dep["on"]
    assert dep_triggers["workflow_run"]["workflows"] == [root_workflows.NAME_CI]
    assert dep["jobs"]["stage-5-approval"]["environment"] == "production"


def test_root_workflow_generator_notices_a_changed_template():
    with pytest.raises(ValueError, match="template changed"):
        root_workflows.render_root("name: Something else\n", "ci", "a/b")
