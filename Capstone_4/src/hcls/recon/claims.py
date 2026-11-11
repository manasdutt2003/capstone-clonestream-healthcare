"""Claim-level reconciliation (Phase 3, tasks 3.1 - 3.3).

Source: Insurance_Claims only. The claim -> bill link is broken on every row (rule A02, D-004), so Billing is never joined.
Every claim lands in exactly one bucket and every submitted dollar is accounted for (the tie-out).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from hcls import config
from hcls.dq.runner import connect

BRIEF_SUBMITTED, BRIEF_RECEIVED = 2_300_000.0, 1_800_000.0  # "Submitted $2.3M, received $1.8M" in the brief
CONFIDENCE = {
    "Paid": "Certain",
    "Adjustment": "Certain (amount); reason Estimated",
    "Denied": "Certain (amount); recovery Estimated",
    "Under appeal": "Estimated",
    "Pipeline": "Estimated",
    "Approved, not yet paid": "Estimated",
    "DQ Hold": "Excluded: needs review",
}
BUCKET_ORDER = [
    "Paid",
    "Adjustment",
    "Denied",
    "Under appeal",
    "Pipeline",
    "Approved, not yet paid",
    "DQ Hold",
]
AGE_BANDS = [
    (0, 90, "0-90 days"),
    (91, 180, "91-180 days"),
    (181, 365, "181-365 days"),
    (366, 10**6, "Over 1 year"),
]
BOOTSTRAP_DRAWS, BOOTSTRAP_SEED = 5000, 2026
MONEY_COLS = ["submitted_amount", "paid_amount", "adjustment_amount", "held_amount"]


def classify(claims: pd.DataFrame) -> pd.DataFrame:
    """One row per claim with bucket, confidence and the dollars split into paid / adjustment / held."""
    con = connect({"Insurance_Claims": claims})
    sql = (config.project_root() / "sql" / "recon" / "claims_buckets.sql").read_text(encoding="utf-8")
    df = con.execute(sql).df()
    con.close()
    paid = df["bucket"].eq("Paid")
    df["paid_amount"] = np.where(paid, df["approved_amount"], 0.0)
    df["adjustment_amount"] = np.where(paid, df["submitted_amount"] - df["approved_amount"], 0.0)
    df["held_amount"] = np.where(df["bucket"].eq("DQ Hold"), df["submitted_amount"].fillna(0.0), 0.0)
    df["confidence"] = df["bucket"].map(CONFIDENCE)
    df["gap"] = df["adjustment_amount"]
    for c in ("hold_reason", "date_flags"):
        df[c] = df[c].fillna("")
    df["dq_flags"] = [
        "; ".join(x for x in (h, f) if x) for h, f in zip(df["hold_reason"], df["date_flags"], strict=True)
    ]
    return df


def _money_sum(s: pd.Series) -> float:
    return round(float(s.fillna(0).sum()), 2)


def bucket_summary(detail: pd.DataFrame) -> pd.DataFrame:
    """Bucket totals. Paid + Adjustment split the submitted dollars of paid claims, so the 'submitted' column ties to the total."""
    rows = []
    for b in BUCKET_ORDER:
        d = detail[detail["bucket"] == b]
        if b == "Paid":
            amt, note = _money_sum(d["paid_amount"]), "Approved amount on approved claims with a paid date"
        elif b == "Adjustment":
            d = detail[detail["bucket"] == "Paid"]
            amt, note = (
                _money_sum(d["adjustment_amount"]),
                "Submitted minus approved on paid claims (insurer reduced it)",
            )
        elif b == "DQ Hold":
            amt, note = (
                _money_sum(d["held_amount"]),
                "Impossible amounts or payment dates; held out of every other bucket",
            )
        else:
            amt = _money_sum(d["submitted_amount"])
            note = {
                "Denied": "Submitted amount of denied claims",
                "Under appeal": "Submitted amount; outcome unknown",
                "Pipeline": "Submitted amount; insurer has not decided",
                "Approved, not yet paid": "Approved but no paid date",
            }[b]
        rows.append(
            {
                "bucket": b,
                "claims": int(len(d)),
                "amount": amt,
                "confidence": CONFIDENCE[b],
                "what_it_is": note,
            }
        )
    return pd.DataFrame(rows)


def tie_out(detail: pd.DataFrame) -> dict:
    """Σ(bucket dollars) must equal Σ(submitted). Returns the pieces and whether they tie to the cent."""
    total = _money_sum(detail["submitted_amount"])
    summ = bucket_summary(detail).set_index("bucket")["amount"]
    parts = float(summ.sum())
    return {
        "total_submitted": total,
        "buckets_total": round(parts, 2),
        "difference": round(total - parts, 2),
        "ties": abs(total - parts) < 0.005,
        "claims_total": int(len(detail)),
        "claims_in_buckets": int(bucket_summary(detail)["claims"].sum() - (detail["bucket"] == "Paid").sum()),
    }


def approval_ratio(detail: pd.DataFrame) -> float:
    paid = detail[detail["bucket"] == "Paid"]
    sub = paid["submitted_amount"].sum()
    return float(paid["approved_amount"].sum() / sub) if sub else 0.0


def expected_value(detail: pd.DataFrame, draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED) -> dict:
    """Expected approved dollars on the pipeline: pipeline x P(approved) x (approved / submitted on approved claims).

    P(approved) is the dollar share of decided claims (approved vs denied) that were approved. A bootstrap over the decided
    claims (fixed seed, so reproducible) gives a 90% range. The older Finance Flash figure (pipeline x ratio) assumed no
    claim would ever be denied; it is kept as the ceiling.
    """
    pipe = float(detail.loc[detail["bucket"] == "Pipeline", "submitted_amount"].sum())
    ok = detail[detail["bucket"].isin(["Paid", "Approved, not yet paid"])]
    denied = detail[detail["bucket"] == "Denied"]
    ratio = approval_ratio(detail)
    ok_sub, den_sub = float(ok["submitted_amount"].sum()), float(denied["submitted_amount"].sum())
    share_usd = ok_sub / (ok_sub + den_sub) if ok_sub + den_sub else 0.0
    n_ok, n_den = len(ok), len(denied)
    share_count = n_ok / (n_ok + n_den) if n_ok + n_den else 0.0
    out = {
        "pipeline_submitted": round(pipe, 2),
        "approval_ratio": ratio,
        "approval_share_dollars": share_usd,
        "approval_share_count": share_count,
        "decided_claims": n_ok + n_den,
        "expected": round(pipe * share_usd * ratio, 2),
        "ceiling_no_denials": round(pipe * ratio, 2),
    }
    pool = detail[detail["bucket"].isin(["Paid", "Approved, not yet paid", "Denied"])].copy()
    if len(pool) < 10 or n_ok == 0 or n_den == 0:
        out.update(low=None, high=None)
        return out
    sub = pool["submitted_amount"].to_numpy()
    appr = pool["approved_amount"].fillna(0).to_numpy()
    is_ok = pool["bucket"].isin(["Paid", "Approved, not yet paid"]).to_numpy()
    is_paid = (pool["bucket"] == "Paid").to_numpy()
    rng = np.random.default_rng(seed)
    n = len(pool)
    est = []
    for _ in range(draws):
        i = rng.integers(0, n, n)
        s_ok = sub[i][is_ok[i]].sum()
        s_all = sub[i].sum()
        p_sub = sub[i][is_paid[i]].sum()
        if s_all <= 0 or p_sub <= 0:
            continue
        est.append(pipe * (s_ok / s_all) * (appr[i][is_paid[i]].sum() / p_sub))
    out["low"] = round(float(np.percentile(est, 5)), 2)
    out["high"] = round(float(np.percentile(est, 95)), 2)
    return out


def pipeline_aging(detail: pd.DataFrame) -> pd.DataFrame:
    """How long have open claims been waiting? Age = as-of date minus submitted date."""
    pipe = detail[detail["bucket"] == "Pipeline"]
    rows = []
    for lo, hi, label in AGE_BANDS:
        d = pipe[(pipe["age_days"] >= lo) & (pipe["age_days"] <= hi)]
        rows.append({"age": label, "claims": int(len(d)), "submitted": _money_sum(d["submitted_amount"])})
    d = pipe[pipe["age_days"].isna()]
    rows.append(
        {
            "age": "Submitted date missing or in the future",
            "claims": int(len(d)),
            "submitted": _money_sum(d["submitted_amount"]),
        }
    )
    return pd.DataFrame(rows)


def brief_reconciliation(detail: pd.DataFrame) -> pd.DataFrame:
    """The brief says 'submitted $2.3M, received $1.8M'. Compare with what the data says."""
    appr = detail[detail["bucket"].isin(["Paid", "Adjustment"])]
    sub = float(appr["submitted_amount"].sum())
    got = float(appr["paid_amount"].sum())
    rows = [
        ("Submitted on approved claims", BRIEF_SUBMITTED, sub),
        ("Received (approved amount)", BRIEF_RECEIVED, got),
        ("Gap (submitted - received)", BRIEF_SUBMITTED - BRIEF_RECEIVED, sub - got),
    ]
    return pd.DataFrame(
        [
            {
                "measure": m,
                "brief": b,
                "data": round(d, 2),
                "difference": round(d - b, 2),
                "difference_pct": round(100 * (d - b) / b, 1),
            }
            for m, b, d in rows
        ]
    )


def exceptions(detail: pd.DataFrame) -> pd.DataFrame:
    """Claims held out of the buckets, plus claims that stay in their bucket but carry a date problem."""
    held = detail[detail["bucket"] == "DQ Hold"].assign(treatment="Held out of all other buckets")
    flagged = detail[(detail["bucket"] != "DQ Hold") & (detail["date_flags"] != "")].assign(
        treatment="Stays in its bucket; date problem only"
    )
    cols = [
        "treatment",
        "claim_id",
        "claim_number",
        "patient_id",
        "claim_status",
        "bucket",
        "submitted_amount",
        "approved_amount",
        "submitted_date",
        "approved_date",
        "paid_date",
        "dq_flags",
        "source_row",
    ]
    return pd.concat([held, flagged])[cols].reset_index(drop=True)


def date_flag_effect(detail: pd.DataFrame) -> dict:
    """If Finance chose to distrust every claim with a date problem, how far would the certain Paid number move?"""
    paid = detail[detail["bucket"] == "Paid"]
    clean = paid[paid["date_flags"] == ""]
    return {
        "paid_claims": int(len(paid)),
        "paid_claims_with_date_flag": int((paid["date_flags"] != "").sum()),
        "paid_all": _money_sum(paid["paid_amount"]),
        "paid_without_flagged": _money_sum(clean["paid_amount"]),
    }


# ----------------------------------------------------------------------------- the over-charging question (task 3.5)

DATA_NEEDED = [
    "The key mapping that links `Insurance_Claims.billing_id` to the bill it was raised for (from the ETL owner), or a corrected extract.",
    "A re-run of the claim-to-bill link after the key fix, checked first on patient (same patient on both sides).",
    "The insurer remittance (835) or payment file, to confirm what was actually paid per claim and when.",
    "A rule from Compliance for what counts as over-charging (patient billed more than the insurer's approved amount, or more than the contracted rate).",
    "Patient-level payment records (what each patient was actually charged and paid), which this data set does not contain.",
]


def overcharge_evidence(frames: dict[str, pd.DataFrame]) -> dict:
    """The numbers behind 'not determinable', recomputed from the data so the text cannot drift."""
    from hcls.rootcause import evidence

    con = connect(frames)
    try:
        lh = evidence.run_sql("link_health", con).set_index("link")
        amt = evidence.run_sql("claim_bill_amounts", con).iloc[0]
        has_bill = evidence.run_sql("claim_patient_has_bill", con).iloc[0]
    finally:
        con.close()
    row = lh.loc["Insurance_Claims -> Billing"]
    return {
        "linked_claims": int(row["linked_rows"]),
        "same_patient": int(row["same_patient"]),
        "median_ratio": float(amt["median_ratio"]),
        "within_25_percent": int(amt["within_25_percent"]),
        "pairs": int(amt["pairs"]),
        "claims_whose_patient_has_a_bill": int(has_bill["claims_whose_patient_has_a_bill"]),
    }


def overcharge_reasons(ev: dict) -> list[str]:
    return [
        f"The claim-to-bill link points at a bill for the same patient in {ev['same_patient']} of {ev['linked_claims']} claims.",
        f"A claim's submitted amount is a median {ev['median_ratio']:.0f}x the bill it points at; only {ev['within_25_percent']} of {ev['pairs']} are within 25%.",
        f"Only {ev['claims_whose_patient_has_a_bill']} of {ev['linked_claims']} claim patients have any bill at all, so most claims cannot be matched even by patient.",
        "Any refund figure built on this link would look precise and be wrong (DECISIONS D-004, D-020).",
    ]
