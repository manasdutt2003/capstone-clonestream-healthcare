"""Finance workbook (Phase 3, task 3.4): Read Me, Claims Summary, Customer Detail, DQ Exceptions. Produced by code only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from hcls import config
from hcls.dq.scorecard import git_sha
from hcls.recon import claims as C

HEADER_FILL = PatternFill("solid", fgColor="075056")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14, color="075056")
BOLD = Font(bold=True)
GREEN, AMBER, RED = (PatternFill("solid", fgColor=c) for c in ("C6EFCE", "FFEB9C", "FFC7CE"))
MONEY = "#,##0.00;[Red]-#,##0.00"
PCT = "0.0%"
DETAIL_COLS = [
    ("claim_id", "Claim ID"),
    ("claim_number", "Claim number"),
    ("patient_id", "Patient ID"),
    ("claim_status", "Status"),
    ("submitted_amount", "Submitted"),
    ("approved_amount", "Approved"),
    ("gap", "Gap (submitted - approved, paid claims)"),
    ("bucket", "Bucket"),
    ("confidence", "Confidence"),
    ("dq_flags", "DQ flags"),
    ("submitted_date", "Submitted date"),
    ("approved_date", "Approved date"),
    ("paid_date", "Paid date"),
    ("source_row", "Source row (Excel)"),
]


def _header(ws, row: int, labels: list[str]) -> None:
    for i, label in enumerate(labels, start=1):
        c = ws.cell(row=row, column=i, value=label)
        c.fill, c.font = HEADER_FILL, HEADER_FONT
        c.alignment = Alignment(wrap_text=True, vertical="center")


def _widths(ws, widths: dict[str, float]) -> None:
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def _clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime().date()
    return v.item() if hasattr(v, "item") else v


def _table(
    ws, start: int, frame: pd.DataFrame, labels: list[str], formats: dict[int, str] | None = None
) -> int:
    """Write a header and rows; return the next free row."""
    _header(ws, start, labels)
    for r, row in enumerate(frame.itertuples(index=False), start=start + 1):
        for c, v in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=_clean(v))
            if formats and c in formats:
                cell.number_format = formats[c]
    return start + len(frame) + 1


def _section(ws, row: int, text: str) -> int:
    ws.cell(row=row, column=1, value=text).font = Font(bold=True, size=12, color="075056")
    return row + 1


def _summary_sheet(ws, detail, ev_value, tie, aging, brief, overcharge, flash_gap) -> None:
    ws["A1"] = "CloneStream Healthcare: claims reconciliation"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = f"As of {config.as_of_date().isoformat()}. Source: Insurance_Claims only (no join to Billing)."
    r = _section(ws, 4, "1. Where every claim dollar sits")
    summ = C.bucket_summary(detail)
    end = _table(
        ws,
        r,
        summ[["bucket", "claims", "amount", "confidence", "what_it_is"]],
        ["Bucket", "Claims", "Amount ($)", "Confidence", "What it is"],
        {3: MONEY},
    )
    ws.cell(row=end, column=1, value="Total").font = BOLD
    ws.cell(row=end, column=3, value=tie["buckets_total"]).number_format = MONEY
    ws.cell(row=end, column=2, value=tie["claims_total"]).font = BOLD
    ws.cell(row=end + 1, column=1, value="Total submitted (all claims)")
    ws.cell(row=end + 1, column=3, value=tie["total_submitted"]).number_format = MONEY
    ws.cell(row=end + 2, column=1, value="Tie-out difference").font = BOLD
    ws.cell(row=end + 2, column=3, value=tie["difference"]).number_format = MONEY
    ws.cell(row=end + 2, column=4, value="Ties to the cent" if tie["ties"] else "DOES NOT TIE: investigate")
    ws.cell(
        row=end + 3,
        column=1,
        value="Paid and Adjustment together equal the submitted dollars of the paid claims; the claim count is shown once.",
    ).font = Font(italic=True)
    r = _section(ws, end + 5, "2. Expected value of the pipeline (estimate)")
    rows = [
        ("Pipeline submitted (insurer has not decided)", ev_value["pipeline_submitted"], MONEY),
        ("Share of decided claims that were approved (by dollars)", ev_value["approval_share_dollars"], PCT),
        ("Approved amount / submitted amount on paid claims", ev_value["approval_ratio"], PCT),
        ("Expected approved amount", ev_value["expected"], MONEY),
        ("Low (5th percentile of 5,000 resamples)", ev_value["low"], MONEY),
        ("High (95th percentile)", ev_value["high"], MONEY),
        (
            "Ceiling if nothing were ever denied (earlier Finance Flash figure)",
            ev_value["ceiling_no_denials"],
            MONEY,
        ),
    ]
    for label, val, fmt in rows:
        ws.cell(row=r, column=1, value=label)
        c = ws.cell(row=r, column=3, value=val)
        c.number_format = fmt
        r += 1
    ws.cell(
        row=r,
        column=1,
        value="Estimate only. It assumes open claims behave like the decided ones. See the aging table below.",
    ).font = Font(italic=True)
    r = _section(ws, r + 2, "3. How long have open (pipeline) claims been waiting?")
    r = _table(ws, r, aging, ["Age since submission", "Claims", "Submitted ($)"], {3: MONEY})
    r = _section(ws, r + 1, "4. Reconciliation to the brief ('submitted $2.3M, received $1.8M')")
    r = _table(
        ws,
        r,
        brief,
        ["Measure", "Brief ($)", "Data ($)", "Difference ($)", "Difference (%)"],
        {2: MONEY, 3: MONEY, 4: MONEY},
    )
    ws.cell(
        row=r,
        column=1,
        value="We could not reproduce the brief's figures from any cut of the data we tried (by year, by paid date, excluding holds). Use the data's figures.",
    ).font = Font(italic=True)
    r = _section(ws, r + 2, "5. Bridge from the earlier Finance Flash")
    bridge = [
        ("Approved amount on all 100 approved claims, as recorded (Flash)", flash_gap["recorded"]),
        ("Less: approved claims held for data-quality review (see DQ Exceptions)", -flash_gap["held"]),
        ("Paid bucket in this workbook (certain)", flash_gap["recorded"] - flash_gap["held"]),
    ]
    for label, val in bridge:
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=3, value=round(val, 2)).number_format = MONEY
        r += 1
    r = _section(ws, r + 1, "6. Were patients over-charged? Not determinable from this data")
    for line in overcharge["reasons"]:
        ws.cell(row=r, column=1, value="- " + line)
        r += 1
    ws.cell(
        row=r,
        column=1,
        value="Recommendation: place a hold on any refund decision. Re-run once the data below is available.",
    ).font = BOLD
    r = _section(ws, r + 2, "Data needed to answer it")
    for line in C.DATA_NEEDED:
        ws.cell(row=r, column=1, value="- " + line)
        r += 1
    r = _section(ws, r + 1, "7. Assumptions")
    for line in ASSUMPTIONS:
        ws.cell(row=r, column=1, value="- " + line)
        r += 1
    _widths(ws, {"A": 62, "B": 12, "C": 18, "D": 40, "E": 60})


ASSUMPTIONS = [
    "Amounts are read from Insurance_Claims.submitted_amount and approved_amount exactly as recorded; no amount is changed.",
    "Paid = status Approved with a paid date on or before the as-of date. Adjustment = submitted minus approved on those claims.",
    "A claim goes to DQ Hold if its amount or payment date is impossible (negative submitted, approved above submitted, paid after the as-of date). It is not counted in any other bucket.",
    "Date problems alone (approved before submitted, paid before approved, future submitted date) do NOT move a claim: the status and amounts decide the bucket. Dates in this data set are unreliable (see docs/02_root_cause_report.md), so payment timing is not certain.",
    "'Certain' means certain from the claim record. Confirm the Paid total against the insurer remittance / bank before external use.",
    "Pipeline expected value = pipeline submitted x P(approved) x (approved / submitted on paid claims). P(approved) uses decided claims only (approved vs denied); appeals are excluded.",
    "The range comes from 5,000 resamples of the decided claims with a fixed seed, so it is reproducible.",
]


def _detail_sheet(ws, detail: pd.DataFrame) -> None:
    labels = [lbl for _, lbl in DETAIL_COLS]
    _header(ws, 1, labels)
    ws.row_dimensions[1].height = 45
    for r, row in enumerate(detail[[c for c, _ in DETAIL_COLS]].itertuples(index=False), start=2):
        for c, v in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=_clean(v))
            if DETAIL_COLS[c - 1][0] in ("submitted_amount", "approved_amount", "gap"):
                cell.number_format = MONEY
            elif DETAIL_COLS[c - 1][0].endswith("_date"):
                cell.number_format = "yyyy-mm-dd"
    ws.freeze_panes = "A2"
    last = len(detail) + 1
    ws.auto_filter.ref = f"A1:{get_column_letter(len(labels))}{last}"
    conf = f"I2:I{last}"
    ws.conditional_formatting.add(conf, FormulaRule(formula=['LEFT($I2,7)="Certain"'], fill=GREEN))
    ws.conditional_formatting.add(conf, FormulaRule(formula=['LEFT($I2,9)="Estimated"'], fill=AMBER))
    ws.conditional_formatting.add(conf, FormulaRule(formula=['LEFT($I2,8)="Excluded"'], fill=RED))
    _widths(
        ws,
        {
            "A": 10,
            "B": 15,
            "C": 11,
            "D": 11,
            "E": 14,
            "F": 14,
            "G": 18,
            "H": 22,
            "I": 34,
            "J": 50,
            "K": 14,
            "L": 14,
            "M": 14,
            "N": 12,
        },
    )


def _exceptions_sheet(ws, exc: pd.DataFrame) -> None:
    labels = [
        "Treatment",
        "Claim ID",
        "Claim number",
        "Patient ID",
        "Status",
        "Bucket",
        "Submitted",
        "Approved",
        "Submitted date",
        "Approved date",
        "Paid date",
        "Why",
        "Source row (Excel)",
    ]
    _header(ws, 1, labels)
    for r, row in enumerate(exc.itertuples(index=False), start=2):
        for c, v in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=_clean(v))
            if c in (7, 8):
                cell.number_format = MONEY
            elif c in (9, 10, 11):
                cell.number_format = "yyyy-mm-dd"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(labels))}{max(2, len(exc) + 1)}"
    _widths(
        ws,
        {
            "A": 38,
            "B": 10,
            "C": 15,
            "D": 11,
            "E": 11,
            "F": 14,
            "G": 14,
            "H": 14,
            "I": 14,
            "J": 14,
            "K": 14,
            "L": 70,
            "M": 12,
        },
    )


def _readme_sheet(ws, run_ts: str, tie: dict) -> None:
    ws["A1"] = "Read me"
    ws["A1"].font = TITLE_FONT
    rows = [
        ("As-of date", config.as_of_date().isoformat()),
        ("Run timestamp (UTC)", run_ts),
        ("Code version (git commit)", git_sha()),
        ("Generated by", "python -m hcls recon (no manual edits; regenerate rather than edit)"),
        (
            "Source",
            "Insurance_Claims (cleaned layer). Billing is not used: the claim-to-bill link is wrong on every row.",
        ),
        ("Claims in workbook", tie["claims_total"]),
        ("Tie-out", "Buckets add up to total submitted, to the cent" if tie["ties"] else "DOES NOT TIE"),
        ("Personal data", "Patient IDs only. No names or contact details."),
        ("", ""),
        ("Sheets", ""),
        (
            "Claims Summary",
            "Totals by bucket, expected value of open claims, aging, reconciliation to the brief, the over-charging answer, assumptions.",
        ),
        (
            "Customer Detail",
            "One row per claim, with bucket, confidence and data-quality flags. Filter on Bucket or Confidence.",
        ),
        (
            "DQ Exceptions",
            "Claims held out of the buckets, and claims that stay in but carry a date problem.",
        ),
        ("", ""),
        ("Buckets", ""),
        ("Paid", "Approved claim with a paid date. Certain."),
        (
            "Adjustment",
            "Submitted minus approved on paid claims. Amount certain; the reason is not recorded.",
        ),
        ("Denied", "Insurer refused. Amount certain; whether it can be recovered is an estimate."),
        ("Under appeal", "Outcome unknown. Estimated."),
        (
            "Pipeline",
            "Submitted, Pending or In Review with no approved amount. The blank is expected: no decision yet. Estimated.",
        ),
        ("DQ Hold", "Impossible amount or payment date. Held out until someone checks the source."),
        ("", ""),
        ("Confidence colours (Customer Detail)", "Green = Certain, amber = Estimated, red = Excluded."),
    ]
    for r, (a, b) in enumerate(rows, start=3):
        ws.cell(row=r, column=1, value=a).font = BOLD
        ws.cell(row=r, column=2, value=b).alignment = Alignment(wrap_text=True, vertical="top")
    _widths(ws, {"A": 34, "B": 100})


def write_finance_workbook(
    detail: pd.DataFrame, overcharge_ev: dict, path: Path | str | None = None, run_ts: str | None = None
) -> tuple[Path, dict]:
    run_ts = run_ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = (
        Path(path)
        if path
        else config.outputs_dir("finance")
        / f"CloneStream_Claims_Reconciliation_{config.as_of_date().isoformat()}.xlsx"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tie = C.tie_out(detail)
    ev_value = C.expected_value(detail)
    held_approved = float(
        detail.loc[
            (detail["bucket"] == "DQ Hold") & (detail["claim_status"] == "Approved"), "approved_amount"
        ].sum()
    )
    recorded = float(detail.loc[detail["claim_status"] == "Approved", "approved_amount"].sum())
    wb = Workbook()
    ws_sum = wb.active
    ws_sum.title = "Claims Summary"
    _summary_sheet(
        ws_sum,
        detail,
        ev_value,
        tie,
        C.pipeline_aging(detail),
        C.brief_reconciliation(detail),
        {"reasons": C.overcharge_reasons(overcharge_ev)},
        {"recorded": recorded, "held": held_approved},
    )
    _detail_sheet(wb.create_sheet("Customer Detail"), detail)
    _exceptions_sheet(wb.create_sheet("DQ Exceptions"), C.exceptions(detail))
    _readme_sheet(wb.create_sheet("Read Me"), run_ts, tie)
    wb.save(path)
    return path, {"tie": tie, "expected": ev_value}
