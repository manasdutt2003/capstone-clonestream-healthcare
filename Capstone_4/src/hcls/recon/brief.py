"""One-page plain-language finance brief (Phase 3, task 3.6). Every number comes from the same code as the workbook."""

from __future__ import annotations

import pandas as pd

from hcls import config
from hcls.recon import claims as C


def m(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


def m2(x: float) -> str:
    return f"-${-x / 1e6:,.2f}M" if x < 0 else f"${x / 1e6:,.2f}M"


def render_brief(
    detail: pd.DataFrame, overcharge_ev: dict, workbook_name: str, elapsed_s: float | None = None
) -> str:
    tie = C.tie_out(detail)
    ev = C.expected_value(detail)
    summ = C.bucket_summary(detail).set_index("bucket")
    aging = C.pipeline_aging(detail).set_index("age")
    brief = C.brief_reconciliation(detail).set_index("measure")
    exc = C.exceptions(detail)
    held = detail[detail["bucket"] == "DQ Hold"]
    flagged_paid = C.date_flag_effect(detail)
    open_old = int(aging.loc["Over 1 year", "claims"])
    open_n = int(summ.loc["Pipeline", "claims"])
    reasons = C.overcharge_reasons(overcharge_ev)
    held_approved = float(held.loc[held["claim_status"] == "Approved", "approved_amount"].sum())
    L = [
        "# Finance Brief: claims reconciliation",
        "",
        f"*As of {config.as_of_date().isoformat()}. For the CFO and Finance. Detail by claim: `{workbook_name}`. Source: `Insurance_Claims` only.*",
        "",
        "## The answer",
        "",
        f"- **We were paid {m2(summ.loc['Paid', 'amount'])} (certain)** on {m2(summ.loc['Paid', 'amount'] + summ.loc['Adjustment', 'amount'])} of approved claims. "
        f"The insurers reduced the other **{m2(summ.loc['Adjustment', 'amount'])}**; the reason is not recorded.",
        f"- **{m2(summ.loc['Pipeline', 'amount'])} is still being decided** ({open_n} claims, estimated). We expect about **{m2(ev['expected'])}** of it to be approved "
        f"(range {m2(ev['low'])} to {m2(ev['high'])}).",
        f"- **{m2(summ.loc['Denied', 'amount'])} was denied** ({int(summ.loc['Denied', 'claims'])} claims). The amount is certain; how much can be recovered is not known.",
        f"- **{m2(summ.loc['Under appeal', 'amount'])} is under appeal** (estimated, outcome unknown).",
        f"- **{len(held)} claims are held out** ({int((held['claim_status'] == 'Approved').sum())} approved, {int((held['claim_status'] == 'Denied').sum())} denied) because an amount or payment date is impossible. They need checking at the source.",
        f"- **Every dollar is accounted for:** the buckets add up to {m(tie['total_submitted'])} submitted across all {tie['claims_total']} claims"
        f"{', to the cent' if tie['ties'] else ' (DOES NOT TIE: investigate)'}.",
        "",
        "## What is certain and what is estimated",
        "",
        "| Bucket | Claims | Amount | Confidence |",
        "|---|---:|---:|---|",
    ]
    for b in C.BUCKET_ORDER:
        if b == "Approved, not yet paid" and summ.loc[b, "claims"] == 0:
            continue
        L.append(
            f"| {b} | {int(summ.loc[b, 'claims'])} | {m(summ.loc[b, 'amount'])} | {summ.loc[b, 'confidence']} |"
        )
    L += [
        f"| **Total submitted** | **{tie['claims_total']}** | **{m(tie['total_submitted'])}** | |",
        "",
        "## Three things to know before you quote a number",
        "",
        f"1. **This is lower than the earlier Finance Flash on two points.** The Flash said {m2(held_approved + float(summ.loc['Paid', 'amount']))} paid; "
        f"{m2(held_approved)} of that sits on {int((held['claim_status'] == 'Approved').sum())} approved claims with impossible data and is now held. "
        f"The Flash also said about {m2(ev['ceiling_no_denials'])} would be approved from the open claims; that assumed nothing is ever denied, so it is the **ceiling**, not the expectation.",
        f"2. **The open claims are old.** {open_old} of the {open_n} open claims were submitted more than a year ago. Claims waiting that long may never be decided, so treat the {m2(ev['expected'])} as optimistic and ask the claims team which are really in flight.",
        f"3. **Dates in this data are unreliable** ({flagged_paid['paid_claims_with_date_flag']} of {flagged_paid['paid_claims']} paid claims have a date out of order). The amounts and statuses are consistent, so the buckets rest on them. "
        "Do not use the dates for payment timing; confirm the paid total against the insurer remittance or bank before using it outside the company.",
        "",
        "## Were patients over-charged? We cannot say yet",
        "",
        "**Recommendation: hold any refund decision.** Why we cannot answer:",
        "",
        *[f"- {r}" for r in reasons],
        "",
        "What we need to answer it:",
        "",
        *[f"- {d}" for d in C.DATA_NEEDED],
        "",
        "## Reconciling to the brief",
        "",
        f"The brief says submitted {m2(C.BRIEF_SUBMITTED)}, received {m2(C.BRIEF_RECEIVED)}, gap {m(C.BRIEF_SUBMITTED - C.BRIEF_RECEIVED)}. "
        f"The data says submitted {m2(brief.loc['Submitted on approved claims', 'data'])}, received {m2(brief.loc['Received (approved amount)', 'data'])}, "
        f"gap {m(brief.loc['Gap (submitted - received)', 'data'])}. We could not reproduce the brief's figures from any cut of the data we tried "
        "(by year, by paid date, with and without the held claims). Use the data's figures.",
        "",
        "## How this was produced",
        "",
        "`python -m hcls recon` builds the workbook and this brief from the cleaned claims table"
        + (f" in about {elapsed_s:.1f} seconds (limit: 5 minutes)." if elapsed_s is not None else "."),
        f"Nothing is typed by hand. {len(exc)} claims are listed on the `DQ Exceptions` sheet. Method and assumptions: the `Claims Summary` and `Read Me` sheets.",
        "",
    ]
    return "\n".join(L)
