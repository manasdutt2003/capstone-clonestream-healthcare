"""Slack notifications (SPEC section 11; DECISIONS D-040).

Sends the alerts from `outputs/alerts.json`, and job success / failure messages, to Slack through an
*incoming webhook*. Nothing here needs a Slack library: it is the standard library only.

Setup (once): create a Slack app with an incoming webhook, then put the URL in the environment variable
`SLACK_WEBHOOK_URL` (GitHub: Settings > Secrets and variables > Actions). To route one stakeholder to its own channel
add `SLACK_WEBHOOK_URL_FINANCE`, `..._COMPLIANCE`, `..._PATIENTCARE` or `..._OPS`; anything without its own webhook goes
to the default one. See docs/NOTIFICATIONS.md.

Behaviour you can rely on
  * No webhook set       -> dry run: the messages are written to outputs/slack_preview.json and nothing is sent.
  * A failed send        -> logged, retried, and never raises (a Slack outage must not fail the data pipeline).
                            Use `--strict` to make a failed send exit 1.
  * Same alerts as last time -> not sent again (a daily job would otherwise repeat itself); `--force` overrides.
  * Alerts cleared        -> one "all clear" message.
  * The webhook URL is a secret: it is never printed or written to a file, and it must be a Slack host.

Run:  python -m hcls notify [--dry-run] [--force] [--strict]
      python -m hcls notify --job dq-daily --status failed --detail "task dq failed"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

SLACK_HOSTS = ("https://hooks.slack.com/", "https://hooks.slack-gov.com/")
ENV_DEFAULT = "SLACK_WEBHOOK_URL"
GROUPS = ("Finance", "Compliance", "PatientCare", "Ops")
DEFAULTS = {
    "enabled": True,
    "only_on_change": True,
    "notify_when_clear": True,
    "max_alerts_listed": 10,
    "timeout_seconds": 10,
    "retries": 3,
}


# --------------------------------------------------------------------------- settings and routing


def settings(cfg: Mapping | None = None) -> dict:
    if cfg is None:
        from hcls import config

        cfg = config.load_config()
    merged = dict(DEFAULTS)
    merged.update(((cfg.get("notifications") or {}).get("slack")) or {})
    return merged


def valid_webhook(url: str | None) -> bool:
    return bool(url) and url.startswith(SLACK_HOSTS)


def webhook_for(group: str, env: Mapping[str, str] | None = None) -> str | None:
    """The webhook for a stakeholder group: its own variable, else the default, else None."""
    env = os.environ if env is None else env
    own = env.get(f"{ENV_DEFAULT}_{group.upper()}", "").strip()
    return own or env.get(ENV_DEFAULT, "").strip() or None


def route(alerts: list[dict], env: Mapping[str, str] | None = None) -> dict[str | None, list[dict]]:
    """Group alerts by the webhook that should receive them. The key None means no webhook is configured."""
    out: dict[str | None, list[dict]] = {}
    for a in alerts:
        out.setdefault(webhook_for(a.get("notify", "Ops"), env), []).append(a)
    return out


# --------------------------------------------------------------------------- messages (Slack Block Kit)


def fingerprint(alerts: list[dict]) -> str:
    """Stable id of an alert set: same alerts (type, rule, rounded value) give the same id, whatever the order."""
    keys = sorted(f"{a['type']}|{a['rule_id']}|{round(float(a.get('value', 0)), 1)}" for a in alerts)
    return hashlib.sha256("\n".join(keys).encode()).hexdigest()[:16]


def _context(result: Mapping, run_url: str | None) -> str:
    bits = [f"as of {result.get('as_of_date', '?')}", f"commit {str(result.get('git_sha', '?'))[:8]}"]
    if result.get("run_ts"):
        bits.append(f"run {result['run_ts']}")
    if run_url:
        bits.append(f"<{run_url}|open the run>")
    return "  ·  ".join(bits)


def alert_payload(
    result: Mapping, alerts: list[dict], limit: int = 10, run_url: str | None = None, label: str | None = None
) -> dict:
    n = len(alerts)
    head = f"CloneStream data quality: {n} alert{'s' if n != 1 else ''}" + (f" for {label}" if label else "")
    shown = alerts[:limit]
    lines = [f"• *{a['rule_id']}* ({a.get('notify', 'Ops')}, {a['type']}): {a['message']}" for a in shown]
    if n > limit:
        lines.append(f"…and {n - limit} more in outputs/alerts.json")
    return {
        "text": f":rotating_light: {head}",  # shown in notifications and by clients without blocks
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f":rotating_light: {head}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": _context(result, run_url)}]},
        ],
    }


def clear_payload(result: Mapping, run_url: str | None = None) -> dict:
    text = "CloneStream data quality: all clear, no alerts in the latest run"
    return {
        "text": f":white_check_mark: {text}",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":white_check_mark: *{text}*"}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": _context(result, run_url)}]},
        ],
    }


def job_payload(job: str, status: str, detail: str = "", run_url: str | None = None) -> dict:
    ok = status.lower() in {"ok", "success", "succeeded"}
    icon = ":white_check_mark:" if ok else ":x:"
    text = f"CloneStream job {job}: {'succeeded' if ok else 'FAILED'}"
    body = f"{icon} *{text}*" + (f"\n{detail}" if detail else "")
    blocks: list[dict] = [{"type": "section", "text": {"type": "mrkdwn", "text": body}}]
    if run_url:
        blocks.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"<{run_url}|open the run>"}]}
        )
    return {"text": f"{icon} {text}", "blocks": blocks}


def github_run_url(env: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if env is None else env
    if env.get("GITHUB_SERVER_URL") and env.get("GITHUB_REPOSITORY") and env.get("GITHUB_RUN_ID"):
        return f"{env['GITHUB_SERVER_URL']}/{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"
    return None


# --------------------------------------------------------------------------- sending


def post(
    url: str,
    payload: dict,
    timeout: float = 10,
    retries: int = 3,
    sleeper: Callable[[float], None] = time.sleep,
    opener: Callable = urllib.request.urlopen,
) -> tuple[bool, str]:
    """POST a message. Returns (ok, short reason). Never raises, never includes the URL in the reason."""
    if not valid_webhook(url):
        return False, "webhook is not a Slack URL"
    data = json.dumps(payload).encode("utf-8")
    reason = "no attempt"
    for attempt in range(1, max(1, retries) + 1):
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with opener(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace").strip()
                if 200 <= resp.status < 300 and body in {"ok", ""}:
                    return True, "sent"
                reason = f"HTTP {resp.status}: {body[:80]}"
        except urllib.error.HTTPError as exc:
            reason = f"HTTP {exc.code}"
            if exc.code in {400, 403, 404, 410}:  # wrong or revoked webhook: retrying will not help
                return False, reason
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = f"network error ({type(exc).__name__})"
        if attempt < retries:
            sleeper(min(2 ** (attempt - 1), 8))
    return False, f"gave up after {retries} attempts: {reason}"


# --------------------------------------------------------------------------- orchestration


def _state_path() -> Path:
    from hcls import config

    return config.outputs_dir() / ".slack_state.json"


def _read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def notify_alerts(
    result: Mapping,
    *,
    env: Mapping[str, str] | None = None,
    cfg: Mapping | None = None,
    state_path: Path | None = None,
    preview_path: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    run_url: str | None = None,
    poster: Callable[..., tuple[bool, str]] | None = None,
) -> dict:
    """Decide what to send for an alerts.json result, send it, and report what happened."""
    from hcls import config

    poster = poster or post
    s = settings(cfg)
    env = os.environ if env is None else env
    state_path = state_path or _state_path()
    preview_path = preview_path or (config.outputs_dir() / "slack_preview.json")
    alerts = list(result.get("alerts", []))
    fp = fingerprint(alerts)
    state = _read_state(state_path)
    info: dict = {
        "status": result.get("status"),
        "alerts": len(alerts),
        "messages": 0,
        "sent": 0,
        "failed": 0,
    }

    if not s["enabled"]:
        return {**info, "outcome": "disabled"}
    if not force and s["only_on_change"] and state.get("fingerprint") == fp:
        return {**info, "outcome": "unchanged"}
    if not alerts and not (state.get("fingerprint") and s["notify_when_clear"]) and not force:
        return {**info, "outcome": "nothing to report"}

    limit = int(s["max_alerts_listed"])
    outbox: list[tuple[str | None, dict]] = []
    if alerts:
        routed = route(alerts, env)
        for url, group in routed.items():
            label = None if len(routed) == 1 else ", ".join(sorted({a["notify"] for a in group}))
            outbox.append((url, alert_payload(result, group, limit, run_url, label)))
    else:
        outbox.append((webhook_for("Ops", env), clear_payload(result, run_url)))

    info["messages"] = len(outbox)
    live = [(u, p) for u, p in outbox if u]
    if dry_run or not live:
        preview_path.write_text(json.dumps([p for _, p in outbox], indent=2), encoding="utf-8")
        return {**info, "outcome": "dry-run", "preview": str(preview_path), "webhook_set": bool(live)}

    for url, payload in live:
        ok, reason = poster(url, payload, timeout=float(s["timeout_seconds"]), retries=int(s["retries"]))
        info["sent" if ok else "failed"] += 1
        if not ok:
            info["last_error"] = reason
    if info["failed"] == 0:  # remember only what was really delivered, so a failed send is retried next run
        state_path.write_text(
            json.dumps({"fingerprint": fp if alerts else "", "status": result.get("status")}),
            encoding="utf-8",
        )
    return {**info, "outcome": "sent" if info["failed"] == 0 else "failed"}


def notify_job(
    job: str,
    status: str,
    detail: str = "",
    *,
    env: Mapping[str, str] | None = None,
    cfg: Mapping | None = None,
    dry_run: bool = False,
    run_url: str | None = None,
    poster: Callable[..., tuple[bool, str]] | None = None,
) -> dict:
    poster = poster or post
    s = settings(cfg)
    env = os.environ if env is None else env
    if not s["enabled"]:
        return {"outcome": "disabled"}
    url = webhook_for("Ops", env)
    payload = job_payload(job, status, detail, run_url or github_run_url(env))
    if dry_run or not url:
        return {"outcome": "dry-run", "payload": payload, "webhook_set": bool(url)}
    ok, reason = poster(url, payload, timeout=float(s["timeout_seconds"]), retries=int(s["retries"]))
    return {"outcome": "sent" if ok else "failed", "reason": reason}


def run(argv: list[str] | None = None, *, out=print) -> int:
    ap = argparse.ArgumentParser(prog="hcls notify", description="Send alerts or a job status to Slack.")
    ap.add_argument("--dry-run", action="store_true", help="build the messages but send nothing")
    ap.add_argument("--force", action="store_true", help="send even if the alerts have not changed")
    ap.add_argument("--strict", action="store_true", help="exit 1 if a message could not be delivered")
    ap.add_argument("--job", help="send a job status message instead of the alerts")
    ap.add_argument("--status", default="ok", help="ok or failed (with --job)")
    ap.add_argument("--detail", default="", help="extra text (with --job)")
    a = ap.parse_args(argv)

    if a.job:
        r = notify_job(a.job, a.status, a.detail, dry_run=a.dry_run)
        out(
            f"notify: job {a.job} {a.status}: {r['outcome']}"
            + (f" ({r['reason']})" if r.get("reason") else "")
        )
        return 1 if (a.strict and r["outcome"] == "failed") else 0

    from hcls import config

    path = config.outputs_dir() / "alerts.json"
    if not path.exists():
        out("notify: outputs/alerts.json not found; run `python -m hcls alerts` first")
        return 1 if a.strict else 0
    result = json.loads(path.read_text(encoding="utf-8"))
    r = notify_alerts(result, force=a.force, dry_run=a.dry_run, run_url=github_run_url())
    extra = {
        "dry-run": f" (no webhook set; preview in {Path(r.get('preview', '')).name})"
        if not r.get("webhook_set")
        else " (--dry-run; nothing sent)",
        "failed": f" ({r.get('last_error', '')})",
    }.get(r["outcome"], "")
    out(f"notify: {r['outcome']}, {r['alerts']} alerts, {r['sent']} sent, {r['failed']} failed{extra}")
    return 1 if (a.strict and r["outcome"] == "failed") else 0


if __name__ == "__main__":
    sys.exit(run())
