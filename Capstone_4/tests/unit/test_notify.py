"""Slack notifications: routing, messages, de-duplication, dry run, retries, and that the webhook never leaks."""

import json
import urllib.error

import pytest

from hcls.monitoring import notify

HOOK = "https://hooks.slack.com/services/T000/B000/SECRETSECRET"
HOOK_FIN = "https://hooks.slack.com/services/T000/B111/FINANCEONLY"
CFG = {"notifications": {"slack": {"retries": 2}}}


def alert(rule, group="Finance", kind="threshold", value=36.0):
    return {
        "type": kind,
        "rule_id": rule,
        "notify": group,
        "value": value,
        "limit": 5,
        "message": f"{rule} fails",
    }


def result(alerts):
    return {
        "as_of_date": "2026-10-21",
        "run_ts": "2026-10-21T19:44:41Z",
        "git_sha": "abcdef123456",
        "status": "ALERT" if alerts else "OK",
        "alerts": alerts,
    }


class Recorder:
    """A stand-in for notify.post that records what would have been sent."""

    def __init__(self, ok=True):
        self.calls, self.ok = [], ok

    def __call__(self, url, payload, **kw):
        self.calls.append((url, payload))
        return (self.ok, "sent" if self.ok else "HTTP 500")


@pytest.fixture
def paths(tmp_path):
    return {"state_path": tmp_path / "state.json", "preview_path": tmp_path / "preview.json"}


# ---- settings, URLs and routing


def test_only_slack_hosts_are_accepted():
    assert notify.valid_webhook(HOOK)
    assert not notify.valid_webhook("https://evil.example.com/hook")
    assert not notify.valid_webhook("http://hooks.slack.com/services/x")  # plain http
    assert not notify.valid_webhook("")
    assert not notify.valid_webhook(None)


def test_each_group_uses_its_own_webhook_else_the_default():
    env = {"SLACK_WEBHOOK_URL": HOOK, "SLACK_WEBHOOK_URL_FINANCE": HOOK_FIN}
    assert notify.webhook_for("Finance", env) == HOOK_FIN
    assert notify.webhook_for("Compliance", env) == HOOK
    assert notify.webhook_for("Finance", {}) is None


def test_routing_splits_alerts_by_webhook():
    env = {"SLACK_WEBHOOK_URL": HOOK, "SLACK_WEBHOOK_URL_FINANCE": HOOK_FIN}
    routed = notify.route([alert("C01"), alert("A30", "PatientCare"), alert("A02", "Finance")], env)
    assert {u: [a["rule_id"] for a in g] for u, g in routed.items()} == {
        HOOK_FIN: ["C01", "A02"],
        HOOK: ["A30"],
    }


# ---- messages


def test_alert_message_lists_alerts_and_caps_the_list():
    many = [alert(f"R{i}") for i in range(12)]
    p = notify.alert_payload(result(many), many, limit=10)
    text = p["blocks"][1]["text"]["text"]
    assert text.count("•") == 10 and "and 2 more" in text
    assert "12 alerts" in p["text"] and "R0" in text


def test_message_carries_context_but_no_url_or_secret():
    p = json.dumps(
        notify.alert_payload(
            result([alert("C01")]), [alert("C01")], run_url="https://github.com/x/actions/runs/1"
        )
    )
    assert "2026-10-21" in p and "abcdef12" in p and "actions/runs/1" in p
    assert "hooks.slack.com" not in p


def test_job_message_marks_failure():
    bad = notify.job_payload("dq-daily", "failed", "task dq failed")
    good = notify.job_payload("dq-daily", "ok")
    assert "FAILED" in bad["text"] and ":x:" in bad["text"] and "task dq failed" in json.dumps(bad)
    assert "succeeded" in good["text"]


def test_fingerprint_ignores_order_and_tiny_changes_but_sees_real_ones():
    a, b = alert("C01"), alert("A30", "PatientCare", value=100.0)
    assert notify.fingerprint([a, b]) == notify.fingerprint([b, a])
    assert notify.fingerprint([a]) == notify.fingerprint([alert("C01", value=36.04)])
    assert notify.fingerprint([a]) != notify.fingerprint([alert("C01", value=40.0)])
    assert notify.fingerprint([a]) != notify.fingerprint([a, b])


def test_github_run_url():
    env = {"GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "7"}
    assert notify.github_run_url(env) == "https://github.com/o/r/actions/runs/7"
    assert notify.github_run_url({}) is None


# ---- orchestration


def test_no_webhook_means_dry_run_and_a_preview_file(paths):
    rec = Recorder()
    r = notify.notify_alerts(result([alert("C01")]), env={}, cfg=CFG, poster=rec, **paths)
    assert r["outcome"] == "dry-run" and r["webhook_set"] is False and rec.calls == []
    assert json.loads(paths["preview_path"].read_text())[0]["text"].startswith(":rotating_light:")
    assert not paths["state_path"].exists()  # nothing was delivered, so nothing is remembered


def test_explicit_dry_run_sends_nothing_even_with_a_webhook(paths):
    rec = Recorder()
    r = notify.notify_alerts(
        result([alert("C01")]), env={"SLACK_WEBHOOK_URL": HOOK}, cfg=CFG, dry_run=True, poster=rec, **paths
    )
    assert r["outcome"] == "dry-run" and r["webhook_set"] is True and rec.calls == []


def test_sends_once_then_stays_quiet_until_the_alerts_change(paths):
    env, rec = {"SLACK_WEBHOOK_URL": HOOK}, Recorder()
    first = notify.notify_alerts(result([alert("C01")]), env=env, cfg=CFG, poster=rec, **paths)
    again = notify.notify_alerts(result([alert("C01")]), env=env, cfg=CFG, poster=rec, **paths)
    changed = notify.notify_alerts(
        result([alert("C01"), alert("A02")]), env=env, cfg=CFG, poster=rec, **paths
    )
    forced = notify.notify_alerts(
        result([alert("C01"), alert("A02")]), env=env, cfg=CFG, poster=rec, force=True, **paths
    )
    assert [first["outcome"], again["outcome"], changed["outcome"], forced["outcome"]] == [
        "sent",
        "unchanged",
        "sent",
        "sent",
    ]
    assert len(rec.calls) == 3


def test_all_clear_is_sent_once_after_alerts_and_not_before(paths):
    env, rec = {"SLACK_WEBHOOK_URL": HOOK}, Recorder()
    assert (
        notify.notify_alerts(result([]), env=env, cfg=CFG, poster=rec, **paths)["outcome"]
        == "nothing to report"
    )
    notify.notify_alerts(result([alert("C01")]), env=env, cfg=CFG, poster=rec, **paths)
    clear = notify.notify_alerts(result([]), env=env, cfg=CFG, poster=rec, **paths)
    assert clear["outcome"] == "sent" and "all clear" in rec.calls[-1][1]["text"]
    assert (
        notify.notify_alerts(result([]), env=env, cfg=CFG, poster=rec, **paths)["outcome"]
        == "nothing to report"
    )


def test_a_failed_send_is_reported_and_retried_next_run(paths):
    env = {"SLACK_WEBHOOK_URL": HOOK}
    bad = notify.notify_alerts(result([alert("C01")]), env=env, cfg=CFG, poster=Recorder(ok=False), **paths)
    assert bad["outcome"] == "failed" and bad["failed"] == 1 and not paths["state_path"].exists()
    ok = notify.notify_alerts(result([alert("C01")]), env=env, cfg=CFG, poster=Recorder(), **paths)
    assert ok["outcome"] == "sent"


def test_alerts_for_two_webhooks_become_two_messages(paths):
    env, rec = {"SLACK_WEBHOOK_URL": HOOK, "SLACK_WEBHOOK_URL_FINANCE": HOOK_FIN}, Recorder()
    r = notify.notify_alerts(
        result([alert("C01"), alert("A30", "PatientCare")]), env=env, cfg=CFG, poster=rec, **paths
    )
    assert r["messages"] == 2 and {u for u, _ in rec.calls} == {HOOK, HOOK_FIN}
    assert all("for " in p["text"] for _, p in rec.calls)  # each says which group it is for


def test_disabled_sends_nothing(paths):
    rec = Recorder()
    cfg = {"notifications": {"slack": {"enabled": False}}}
    r = notify.notify_alerts(
        result([alert("C01")]), env={"SLACK_WEBHOOK_URL": HOOK}, cfg=cfg, poster=rec, **paths
    )
    assert r["outcome"] == "disabled" and rec.calls == []


def test_job_notification_dry_run_and_send():
    rec = Recorder()
    assert notify.notify_job("dq", "failed", env={}, cfg=CFG, poster=rec)["outcome"] == "dry-run"
    r = notify.notify_job("dq", "failed", "boom", env={"SLACK_WEBHOOK_URL": HOOK}, cfg=CFG, poster=rec)
    assert r["outcome"] == "sent" and "FAILED" in rec.calls[0][1]["text"]


# ---- the HTTP layer


class Resp:
    def __init__(self, status=200, body="ok"):
        self.status, self._body = status, body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body.encode()


def test_post_succeeds_on_ok():
    seen = []

    def opener(req, timeout):
        seen.append((req.full_url, req.get_method(), json.loads(req.data)))
        return Resp()

    ok, why = notify.post(HOOK, {"text": "hi"}, opener=opener, sleeper=lambda s: None)
    assert ok and why == "sent" and seen == [(HOOK, "POST", {"text": "hi"})]


def test_post_retries_a_flaky_network_then_succeeds():
    calls = {"n": 0}

    def opener(req, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("down")
        return Resp()

    sleeps = []
    ok, _ = notify.post(HOOK, {}, retries=3, opener=opener, sleeper=sleeps.append)
    assert ok and calls["n"] == 3 and sleeps == [1, 2]


def test_post_gives_up_quietly_and_never_exposes_the_url():
    def opener(req, timeout):
        raise urllib.error.URLError(f"cannot reach {req.full_url}")

    ok, why = notify.post(HOOK, {}, retries=2, opener=opener, sleeper=lambda s: None)
    assert (
        not ok and "gave up after 2 attempts" in why and "SECRET" not in why and "hooks.slack.com" not in why
    )


def test_post_does_not_retry_a_revoked_webhook():
    calls = {"n": 0}

    def opener(req, timeout):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 404, "no_service", {}, None)

    ok, why = notify.post(HOOK, {}, retries=3, opener=opener, sleeper=lambda s: None)
    assert not ok and why == "HTTP 404" and calls["n"] == 1


def test_post_refuses_a_non_slack_url_without_calling_anything():
    def opener(*a, **k):
        raise AssertionError("must not be called")

    ok, why = notify.post("https://evil.example.com/x", {}, opener=opener)
    assert not ok and "not a Slack URL" in why


# ---- the command line


def test_run_job_status_dry_run(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    lines = []
    assert notify.run(["--job", "dq-daily", "--status", "failed"], out=lines.append) == 0
    assert "dry-run" in lines[0]


def test_run_strict_fails_when_delivery_fails(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", HOOK)
    monkeypatch.setattr(notify, "post", lambda *a, **k: (False, "HTTP 500"))
    assert notify.run(["--job", "x", "--status", "failed", "--strict"], out=lambda s: None) == 1
    assert (
        notify.run(["--job", "x", "--status", "failed"], out=lambda s: None) == 0
    )  # default: never breaks the pipeline
