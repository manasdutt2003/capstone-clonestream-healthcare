"""Run-level audit trail (Phase 5, task 5.1): who ran what, when, with what result, and a fingerprint of every output.

`audit_log.csv` gets one row per pipeline command run (appended, never rewritten). `audit_outputs.csv` is the manifest of
every gold file with its SHA-256, so an auditor can prove an output was not edited after the run.
"""

from __future__ import annotations

import datetime as dt
import getpass
import hashlib
import uuid
from pathlib import Path

import pandas as pd

from hcls import config
from hcls.dq.scorecard import git_sha

LOG_COLUMNS = [
    "run_id",
    "job",
    "git_sha",
    "user",
    "started_utc",
    "ended_utc",
    "seconds",
    "status",
    "rows_in",
    "rows_out",
    "rules_run",
    "rules_failed",
    "rules_passed",
    "outputs_digest",
    "output_files",
]
EXCLUDE = {"audit_log.csv", "audit_outputs.csv"}  # the log cannot fingerprint itself


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def manifest(gold: Path) -> pd.DataFrame:
    """SHA-256 and size of every file under gold/, in a stable order."""
    rows = []
    for p in sorted(gold.rglob("*")):
        if p.is_file() and p.name not in EXCLUDE:
            rows.append(
                {"file": p.relative_to(gold).as_posix(), "sha256": sha256_file(p), "bytes": p.stat().st_size}
            )
    return pd.DataFrame(rows, columns=["file", "sha256", "bytes"])


def digest(man: pd.DataFrame) -> str:
    """One hash over the whole manifest: it changes if any output changes."""
    h = hashlib.sha256()
    for _, r in man.iterrows():
        h.update(f"{r['file']}:{r['sha256']}\n".encode())
    return h.hexdigest()


def _rows(layer: str) -> int | None:
    import pyarrow.parquet as pq

    folder = config.outputs_dir(layer)
    files = sorted(folder.glob("*.parquet"))
    return sum(pq.ParquetFile(f).metadata.num_rows for f in files) if files else None


def _rule_counts(gold: Path) -> tuple[int | None, int | None, int | None]:
    p = gold / "dq_scorecard.csv"
    if not p.exists():
        return None, None, None
    sc = pd.read_csv(p)
    sc = sc[sc["severity"] != "Info"]
    failed = int((sc["rows_failed"] > 0).sum())
    return len(sc), failed, len(sc) - failed


def build_entry(job: str, started: dt.datetime, ended: dt.datetime, status: str) -> dict:
    gold = config.outputs_dir("gold")
    man = manifest(gold)
    run, failed, passed = _rule_counts(gold)
    return {
        "run_id": f"{started:%Y%m%dT%H%M%S}-{job}-{uuid.uuid4().hex[:6]}",
        "job": job,
        "git_sha": git_sha(),
        "user": getpass.getuser(),
        "started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ended_utc": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds": round((ended - started).total_seconds(), 2),
        "status": status,
        "rows_in": _rows("bronze"),
        "rows_out": _rows("silver"),
        "rules_run": run,
        "rules_failed": failed,
        "rules_passed": passed,
        "outputs_digest": digest(man) if len(man) else "",
        "output_files": len(man),
    }


def append_entry(entry: dict) -> Path:
    gold = config.outputs_dir("gold")
    path = gold / "audit_log.csv"
    row = pd.DataFrame([entry], columns=LOG_COLUMNS)
    if path.exists():
        row = pd.concat([pd.read_csv(path), row], ignore_index=True)
    row.to_csv(path, index=False)
    return path


def write_manifest() -> pd.DataFrame:
    gold = config.outputs_dir("gold")
    man = manifest(gold)
    man.to_csv(gold / "audit_outputs.csv", index=False)
    return man


def verify(gold: Path | None = None) -> list[str]:
    """Files whose hash no longer matches the manifest (edited, deleted or added since the last audit run)."""
    gold = gold or config.outputs_dir("gold")
    saved = pd.read_csv(gold / "audit_outputs.csv").set_index("file")["sha256"].to_dict()
    now = manifest(gold).set_index("file")["sha256"].to_dict()
    return sorted(f for f in set(saved) | set(now) if saved.get(f) != now.get(f))
