"""Finance Flash (Phase 1, task 1.10): a one-page, preliminary answer for Finance on day 1.

Reads Insurance_Claims only. It deliberately does not join to Billing, because the
claim -> bill link is broken (rule A02, DECISIONS D-004).
"""

from __future__ import annotations

import pandas as pd

from hcls import config
from hcls.dq.runner import connect

PIPELINE = ("Submitted", "Pending", "In Review")


def flash_tables(claims: pd.DataFrame) -> dict:
    con = connect({"Insurance_Claims": claims})
    sql = (config.project_root() / "sql" / "recon" / "finance_flash.sql").read_text(encoding="utf-8")
    by_status = con.execute(sql).df()
    con.close()
    by_status = by_status.set_index("claim_status")

    def amt(status, col="submitted"):
        return float(by_status.loc[status, col]) if status in by_status.index else 0.0

    approved_sub, approved_amt = amt("Approved"), amt("Approved", "approved")
    ratio = approved_amt / approved_sub if approved_sub else 0.0
    pipeline = sum(amt(s) for s in PIPELINE)
    return {
        "by_status": by_status.reset_index(),
        "approved_submitted": approved_sub,
        "approved_paid": approved_amt,
        "gap": approved_sub - approved_amt,
        "ratio": ratio,
        "pipeline_submitted": pipeline,
        "pipeline_expected": pipeline * ratio,
        "denied": amt("Denied"),
        "appealed": amt("Appealed"),
        "total_submitted": float(by_status["submitted"].sum()),
        "claims_total": int(by_status["claims"].sum()),
        "blank_approved": int(by_status["approved_amount_blank"].sum()),
        "blank_in_pipeline": int(
            sum(by_status.loc[s, "approved_amount_blank"] for s in PIPELINE if s in by_status.index)
        ),
        "anomalies": int(by_status["amount_anomalies"].sum()),
    }


def money(x: float) -> str:
    return f"${x:,.0f}"


def render(t: dict) -> str:
    lines = [
        "# Finance Flash (preliminary)",
        "",
        f"*As of {config.as_of_date().isoformat()}. Source: `Insurance_Claims` only. Prepared for the CFO board pack; "
        "superseded by `docs/03_finance_brief.md` and the reconciliation workbook.*",
        "",
        "## The short answer",
        "",
        f"- **Paid (certain):** the {int(t['by_status'].set_index('claim_status').loc['Approved', 'claims'])} approved claims asked for "
        f"**{money(t['approved_submitted'])}** and were approved for **{money(t['approved_paid'])}**. "
        f"The **{money(t['gap'])}** difference is what the insurers reduced or did not approve (the reason per claim is not recorded).",
        f"- **Still being decided (estimated):** {t['blank_in_pipeline']} claims worth **{money(t['pipeline_submitted'])}** have no approved amount "
        f"*because the insurer has not decided yet*. If every one were approved at the historical {t['ratio']:.1%} rate it would come to "
        f"**{money(t['pipeline_expected'])}**. That is a **ceiling** (it assumes no denials); the reconciliation brief gives the expected value.",
        f"- **Denied (certain amount, recovery uncertain):** {money(t['denied'])}. **Under appeal (estimated):** {money(t['appealed'])}.",
        f"- **Total submitted across all {t['claims_total']} claims:** {money(t['total_submitted'])}.",
        "",
        "## Where every claim dollar sits",
        "",
        "| Status | Claims | Submitted | Approved | Confidence |",
        "|---|---:|---:|---:|---|",
    ]
    conf = {
        "Approved": "Certain",
        "Denied": "Certain (amount)",
        "Appealed": "Estimated",
        "Submitted": "Estimated",
        "Pending": "Estimated",
        "In Review": "Estimated",
    }
    for _, r in t["by_status"].iterrows():
        approved = money(r["approved"]) if r["claim_status"] in ("Approved",) else "-"
        lines.append(
            f"| {r['claim_status']} | {int(r['claims'])} | {money(r['submitted'])} | {approved} | {conf.get(r['claim_status'], '')} |"
        )
    lines += [
        f"| **Total** | **{t['claims_total']}** | **{money(t['total_submitted'])}** | | |",
        "",
        "## Read this before you quote a number",
        "",
        f"1. **The 'missing approved amounts' are not lost data.** {t['blank_approved']} claims have a blank approved amount; "
        f"{'all' if t['blank_in_pipeline'] == t['blank_approved'] else t['blank_in_pipeline']} of them are still Submitted, Pending or In Review. "
        "A blank is expected until the insurer replies.",
        f"2. **{t['anomalies']} claims have impossible amounts** (a negative submitted amount, or approved above submitted). "
        "They are included above *as recorded*; the Wednesday workbook holds them out separately.",
        "3. **The brief's $2.3M / $1.8M do not match the data.** The data says "
        f"{money(t['approved_submitted'])} / {money(t['approved_paid'])}. Use the data's figures.",
        "4. **We cannot yet say whether patients were over-charged.** The link from claims to bills is wrong on every row "
        "(rule A02), so any claim-vs-bill comparison would look precise and be wrong.",
        "",
        "*Confidence: Certain = read directly from a decided claim. Estimated = depends on an insurer decision that has not happened.*",
    ]
    return "\n".join(lines) + "\n"


def write_flash(claims: pd.DataFrame) -> tuple[dict, str]:
    t = flash_tables(claims)
    text = render(t)
    (config.docs_dir("stakeholder_memos") / "00_finance_flash.md").write_text(text, encoding="utf-8")
    t["by_status"].to_csv(config.outputs_dir("gold") / "finance_flash_by_status.csv", index=False)
    return t, text
