"""Command line entry point:  python -m hcls <ingest|clean|dq|flash|rootcause|recon|backfill|validate|alerts|notify|audit|powerbi|docs|all>"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time

from hcls import config, ingest, reports, standardise
from hcls.dq import runner, scorecard
from hcls.export_clean import write_clean_workbook
from hcls.recon import flash


def _bronze():
    b = ingest.load_layer("bronze")
    return b or ingest.ingest()


def _silver():
    s = ingest.load_layer("silver")
    if s:
        return s
    cmd_clean()
    return ingest.load_layer("silver")


def cmd_ingest() -> None:
    b = ingest.ingest()
    print(f"ingest: {len(b)} sheets, {sum(len(v) for v in b.values()):,} rows -> outputs/bronze")


def cmd_clean() -> None:
    bronze = _bronze()
    silver, changes = standardise.standardise(bronze)
    ingest.save_layer("silver", silver)
    gold = config.outputs_dir("gold")
    changes.to_csv(gold / "change_log.csv", index=False)
    standardise.cleaning_summary(changes).to_csv(gold / "cleaning_summary.csv", index=False)
    path = write_clean_workbook(silver, changes)
    try:
        shown = path.relative_to(config.project_root())
    except ValueError:
        shown = path
    print(f"clean: {len(changes):,} cells changed; workbook -> {shown}")


def cmd_dq() -> None:
    bronze, silver = _bronze(), _silver()
    gold = config.outputs_dir("gold")
    run_ts = runner.now_utc()
    raw_frames = {k: v for k, v in bronze.items()}
    raw_res, tl, fails = runner.run_rules(raw_frames)
    clean_res, _, clean_fails = runner.run_rules({k: v for k, v in silver.items() if not k.startswith("_")})
    sc = scorecard.build_scorecard(raw_res, tl, run_ts)
    if (gold / "dq_scorecard.csv").exists():  # keep the last run so drift alerts can compare
        shutil.copyfile(gold / "dq_scorecard.csv", gold / "dq_scorecard_previous.csv")
    sc.to_csv(gold / "dq_scorecard.csv", index=False)
    sc.to_parquet(gold / "dq_scorecard.parquet", index=False)
    scorecard.timeline_table(tl).to_csv(gold / "dq_timeline.csv", index=False)
    scorecard.append_history(sc)
    ri = scorecard.ri_crosscheck(bronze)
    ri.to_csv(gold / "ri_crosscheck.csv", index=False)
    effect = scorecard.cleaning_effect(raw_res, clean_res)
    effect.to_csv(gold / "cleaning_effect.csv", index=False)
    scorecard.build_scorecard(clean_res, tl, run_ts).to_csv(
        gold / "dq_scorecard_after_cleaning.csv", index=False
    )
    import pandas as pd

    changes = (
        pd.read_csv(gold / "change_log.csv")
        if (gold / "change_log.csv").exists()
        else pd.DataFrame(columns=["table", "row_num", "column"])
    )
    flagged = scorecard.add_flags({k: v for k, v in silver.items()}, clean_fails, changes)
    ingest.save_layer("silver", flagged)
    fails.to_csv(gold / "dq_failures_raw.csv", index=False)
    print(
        f"dq: {len(sc)} rules, {int((sc.rows_failed > 0).sum())} with findings; critical: "
        f"{int(((sc.severity == 'Critical') & (sc.rows_failed > 0)).sum())}"
    )


def cmd_flash() -> None:
    silver = _silver()
    t, _ = flash.write_flash(silver["Insurance_Claims"])
    print(
        f"flash: paid {t['approved_paid']:,.0f}, pipeline {t['pipeline_submitted']:,.0f} -> docs/stakeholder_memos/00_finance_flash.md"
    )


def cmd_docs() -> None:
    import pandas as pd

    gold = config.path("outputs") / "gold"
    sc = pd.read_csv(gold / "dq_scorecard.csv")
    tl = pd.read_csv(gold / "dq_timeline.csv")
    ri = pd.read_csv(gold / "ri_crosscheck.csv")
    effect = pd.read_csv(gold / "cleaning_effect.csv")
    changes = pd.read_csv(gold / "change_log.csv")
    summary = pd.read_csv(gold / "cleaning_summary.csv")
    docs = config.docs_dir()
    (docs / "01_dq_scorecard.md").write_text(
        reports.render_scorecard_doc(sc, tl, ri, effect, scorecard.table_summary(sc)), encoding="utf-8"
    )
    bronze, silver = _bronze(), _silver()
    raw_rows = {k: len(v) for k, v in bronze.items()}
    clean_rows = {k: len(v) for k, v in silver.items()}
    (docs / "CLEANING.md").write_text(
        reports.render_cleaning_doc(summary, changes, raw_rows, clean_rows), encoding="utf-8"
    )
    shown = "docs/01_dq_scorecard.md, docs/CLEANING.md"
    if (gold / "backfill_summary.csv").exists() and (gold / "validator_catch.csv").exists():
        from hcls.remediation import plan

        alerts_path = config.path("outputs") / "alerts.json"
        alerts = json.loads(alerts_path.read_text(encoding="utf-8")) if alerts_path.exists() else {}
        viol = pd.read_csv(gold / "validator_violations.csv")
        text = plan.render_plan(
            sc,
            pd.read_csv(gold / "backfill_summary.csv"),
            pd.read_csv(gold / "validator_catch.csv"),
            viol,
            alerts,
            f"run {sc['run_ts'].iloc[0]}, commit {sc['git_sha'].iloc[0]}",
        )
        (docs / "04_remediation_plan.md").write_text(text, encoding="utf-8")
        shown += ", docs/04_remediation_plan.md"
    if (gold / "audit_metrics.csv").exists():
        from hcls.audit import facts, memos, pack

        f = facts.collect(gold)
        memo_dir = docs / "stakeholder_memos"
        memo_dir.mkdir(parents=True, exist_ok=True)
        for fname, fn in memos.MEMOS.items():
            (memo_dir / fname).write_text(fn(f), encoding="utf-8")
        log = gold / "audit_log.csv"
        (docs / "05_audit_pack.md").write_text(
            pack.render(
                f,
                pd.read_csv(log) if log.exists() else pd.DataFrame(),
                pd.read_csv(gold / "audit_metrics.csv"),
            ),
            encoding="utf-8",
        )
        shown += ", docs/05_audit_pack.md, 3 stakeholder memos"
    print(f"docs: {shown}")


def cmd_recon() -> None:
    import time

    import pandas as pd

    from hcls.recon import brief, claims, excel_export

    t0 = time.monotonic()
    silver = _silver()
    detail = claims.classify(silver["Insurance_Claims"])
    gold = config.outputs_dir("gold")
    detail.to_csv(gold / "recon_claims.csv", index=False)
    claims.bucket_summary(detail).to_csv(gold / "recon_buckets.csv", index=False)
    claims.exceptions(detail).to_csv(gold / "recon_exceptions.csv", index=False)
    evid = claims.overcharge_evidence(_bronze())
    sc_path = gold / "dq_scorecard.csv"
    run_ts = pd.read_csv(sc_path)["run_ts"].iloc[0] if sc_path.exists() else None
    path, info = excel_export.write_finance_workbook(detail, evid, run_ts=run_ts)
    elapsed = time.monotonic() - t0
    text = brief.render_brief(detail, evid, path.name, elapsed)
    (config.docs_dir() / "03_finance_brief.md").write_text(text, encoding="utf-8")
    sla = float(config.load_config()["alerts"]["recon_sla_seconds"])
    pd.DataFrame(
        [
            {
                "run_ts": run_ts,
                "step": "recon",
                "seconds": round(elapsed, 2),
                "sla_seconds": sla,
                "within_sla": elapsed <= sla,
            }
        ]
    ).to_csv(gold / "recon_timing.csv", index=False)
    print(
        f"recon: {info['tie']['claims_total']} claims, ties={info['tie']['ties']}, expected pipeline {info['expected']['expected']:,.0f} "
        f"({elapsed:.1f}s) -> {path.name}, docs/03_finance_brief.md"
    )
    if not info["tie"]["ties"]:
        raise SystemExit("recon: buckets do not tie to total submitted")


def cmd_backfill() -> None:
    from hcls.remediation import backfill_sim

    sim = backfill_sim.simulate(_silver())
    gold = config.outputs_dir("gold")
    sim["summary"].to_csv(gold / "backfill_summary.csv", index=False)
    sim["c03"].to_csv(gold / "backfill_c03.csv", index=False)
    sim["c02"].to_csv(gold / "backfill_c02.csv", index=False)
    s = sim["summary"].set_index("rule_id")
    print(
        f"backfill: C03 applied {int(s.loc['C03', 'applied_to_copy'])} of {int(s.loc['C03', 'records_failing_before'])}, "
        f"C02 applied {int(s.loc['C02', 'applied_to_copy'])} of {int(s.loc['C02', 'records_failing_before'])}; source unchanged"
    )


def cmd_validate() -> None:
    from hcls.remediation import validators

    silver = _silver()
    viol = validators.validate(silver)
    catch = validators.catch_report(silver, viol)
    gold = config.outputs_dir("gold")
    viol.to_csv(gold / "validator_violations.csv", index=False)
    catch.to_csv(gold / "validator_catch.csv", index=False)
    print(
        f"validate: {len(validators.CHECKS)} checks; would reject {viol.groupby(['table', 'row_num']).ngroups} distinct rows "
        f"({int((catch['rows_it_would_reject'] > 0).sum())} checks fire)"
    )


def cmd_alerts() -> None:
    import pandas as pd

    from hcls.monitoring import alerts

    gold = config.outputs_dir("gold")
    sc = pd.read_csv(gold / "dq_scorecard.csv")
    prev = (
        pd.read_csv(gold / "dq_scorecard_previous.csv")
        if (gold / "dq_scorecard_previous.csv").exists()
        else None
    )
    timing = pd.read_csv(gold / "recon_timing.csv") if (gold / "recon_timing.csv").exists() else None
    result = alerts.evaluate(sc, prev, timing)
    path = alerts.write_alerts(result)
    print(f"alerts: {result['status']}, {len(result['alerts'])} alerts {result['counts']} -> {path.name}")


_NOTIFY_ARGS: list[str] = []  # extra options for `notify`, set by main()


def cmd_notify() -> None:
    from hcls.monitoring import notify

    code = notify.run(_NOTIFY_ARGS)
    if code:
        raise SystemExit(code)


def cmd_audit() -> None:
    from hcls.audit import audit_log, metrics

    gold = config.outputs_dir("gold")
    m = metrics.append(metrics.compute(gold), gold)
    man = audit_log.write_manifest()
    print(
        f"audit: {m['metric'].nunique()} metrics, {len(man)} output files fingerprinted -> audit_metrics.csv, audit_outputs.csv"
    )


def cmd_powerbi() -> None:
    from hcls.audit import powerbi

    man = powerbi.write()
    print(f"powerbi: {len(man)} tables, no personal data -> outputs/powerbi")


def cmd_rootcause() -> None:
    import pandas as pd

    from hcls.rootcause import evidence

    gold = config.path("outputs") / "gold"
    sc = pd.read_csv(gold / "dq_scorecard.csv")
    failures = pd.read_csv(gold / "dq_failures_raw.csv")
    bronze = _bronze()
    ev = evidence.collect(bronze, sc, failures)
    hyps = evidence.build_hypotheses(ev)
    out = config.outputs_dir("gold", "rootcause")
    for name, df in ev.items():
        df.to_csv(out / f"{name}.csv", index=False)
    pd.DataFrame(hyps).to_csv(out / "hypotheses.csv", index=False)
    label = f"run {sc['run_ts'].iloc[0]}, commit {sc['git_sha'].iloc[0]}"
    (config.docs_dir() / "02_root_cause_report.md").write_text(
        reports.render_root_cause_report(ev, hyps, label), encoding="utf-8"
    )
    verdicts = pd.Series([h["verdict"] for h in hyps]).value_counts().to_dict()
    print(f"rootcause: {len(hyps)} hypotheses {verdicts} -> docs/02_root_cause_report.md")


COMMANDS = {
    "ingest": cmd_ingest,
    "clean": cmd_clean,
    "dq": cmd_dq,
    "flash": cmd_flash,
    "rootcause": cmd_rootcause,
    "recon": cmd_recon,
    "backfill": cmd_backfill,
    "validate": cmd_validate,
    "alerts": cmd_alerts,
    "notify": cmd_notify,
    "audit": cmd_audit,
    "powerbi": cmd_powerbi,
    "docs": cmd_docs,
}


def _run(name: str) -> None:
    """Run one command and append a row to the audit log, whether it succeeds or fails."""
    import datetime as dt

    from hcls.audit import audit_log

    started = dt.datetime.now(dt.timezone.utc)
    status = "ok"
    try:
        COMMANDS[name]()
    except BaseException:
        status = "failed"
        raise
    finally:
        try:
            audit_log.append_entry(
                audit_log.build_entry(name, started, dt.datetime.now(dt.timezone.utc), status)
            )
        except Exception as exc:  # the audit trail must never hide the real result of the run
            print(f"warning: audit log not written: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="hcls", description=__doc__)
    ap.add_argument("command", choices=[*COMMANDS, "all"])
    ap.add_argument(
        "options", nargs=argparse.REMAINDER, help="options for `notify` (see hcls.monitoring.notify)"
    )
    args = ap.parse_args(argv)
    _NOTIFY_ARGS[:] = args.options if args.command == "notify" else []
    start = time.time()
    if args.command == "all":
        for name in (
            "ingest",
            "clean",
            "dq",
            "flash",
            "rootcause",
            "recon",
            "backfill",
            "validate",
            "alerts",
            "notify",
            "audit",
            "powerbi",
            "docs",
        ):
            _run(name)
    else:
        _run(args.command)
    print(f"done in {time.time() - start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
