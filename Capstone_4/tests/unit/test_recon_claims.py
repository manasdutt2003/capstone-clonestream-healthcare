"""Unit tests for the claim reconciliation: buckets, holds, tie-out, expected value, aging."""

import pandas as pd
import pytest

from hcls.recon import claims as C

COLS = [
    "claim_id",
    "patient_id",
    "claim_number",
    "claim_status",
    "submitted_amount",
    "approved_amount",
    "submitted_date",
    "approved_date",
    "paid_date",
]


def mk(*rows):
    """rows: (status, submitted, approved, submitted_date, approved_date, paid_date); '' = blank."""
    data = []
    for i, (status, sub, appr, sd, ad, pd_) in enumerate(rows, start=1):
        data.append([str(i), str(100 + i), f"CLM-{i}", status, sub, appr, sd, ad, pd_])
    df = pd.DataFrame(data, columns=COLS)
    df.insert(0, "_row_num", range(2, len(df) + 2))
    return df


GOOD = ("Approved", "1000", "800", "2024-01-01", "2024-02-01", "2024-03-01")


@pytest.mark.parametrize(
    ("row", "bucket"),
    [
        (GOOD, "Paid"),
        (("Approved", "1000", "800", "2024-01-01", "2024-02-01", ""), "Approved, not yet paid"),
        (("Denied", "500", "0", "2024-01-01", "2024-02-01", ""), "Denied"),
        (("Appealed", "300", "0", "2024-01-01", "2024-02-01", ""), "Under appeal"),
        (("Submitted", "400", "", "2024-01-01", "", ""), "Pipeline"),
        (("Pending", "400", "", "2024-01-01", "", ""), "Pipeline"),
        (("In Review", "400", "", "2024-01-01", "", ""), "Pipeline"),
    ],
)
def test_each_status_lands_in_its_bucket(row, bucket):
    assert C.classify(mk(row)).iloc[0]["bucket"] == bucket


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (("Approved", "-50", "10", "2024-01-01", "2024-02-01", "2024-03-01"), "Negative submitted amount"),
        (("Denied", "-50", "0", "2024-01-01", "2024-02-01", ""), "Negative submitted amount"),
        (
            ("Approved", "100", "300", "2024-01-01", "2024-02-01", "2024-03-01"),
            "Approved amount above submitted amount",
        ),
        (
            ("Approved", "100", "80", "2024-01-01", "2024-02-01", "2027-01-01"),
            "Paid date is after the as-of date",
        ),
        (("Approved", "", "80", "2024-01-01", "2024-02-01", "2024-03-01"), "Submitted amount missing"),
        (("Weird", "100", "", "2024-01-01", "", ""), "Unrecognised claim status"),
        (("", "100", "", "2024-01-01", "", ""), "Unrecognised claim status"),
    ],
)
def test_impossible_money_or_payment_date_goes_to_hold(row, reason):
    r = C.classify(mk(row)).iloc[0]
    assert r["bucket"] == "DQ Hold" and r["hold_reason"] == reason
    assert r["paid_amount"] == 0 and r["adjustment_amount"] == 0


def test_date_only_problems_flag_but_do_not_move_the_money():
    row = (
        "Approved",
        "1000",
        "800",
        "2024-05-01",
        "2024-02-01",
        "2024-01-01",
    )  # approved before submitted, paid before approved
    r = C.classify(mk(row)).iloc[0]
    assert r["bucket"] == "Paid" and r["paid_amount"] == 800 and r["adjustment_amount"] == 200
    assert "Approved before submitted" in r["date_flags"] and "Paid before approved" in r["date_flags"]
    future = C.classify(mk(("Submitted", "400", "", "2027-06-01", "", ""))).iloc[0]
    assert future["bucket"] == "Pipeline" and "Submitted date in the future" in future["date_flags"]
    assert pd.isna(future["age_days"])


def test_paid_and_adjustment_split_the_submitted_dollars():
    d = C.classify(mk(GOOD))
    assert d.loc[0, "paid_amount"] + d.loc[0, "adjustment_amount"] == d.loc[0, "submitted_amount"]
    assert d.loc[0, "confidence"] == "Certain"


def test_every_dollar_ties_out_including_negatives_and_holds():
    d = C.classify(
        mk(
            GOOD,
            ("Denied", "500", "0", "2024-01-01", "2024-02-01", ""),
            ("Appealed", "300", "0", "2024-01-01", "2024-02-01", ""),
            ("Pending", "400", "", "2024-01-01", "", ""),
            ("Approved", "-50", "10", "2024-01-01", "2024-02-01", "2024-03-01"),
            ("Approved", "100", "80", "2024-01-01", "2024-02-01", "2027-01-01"),
            ("Weird", "7", "", "2024-01-01", "", ""),
        )
    )
    t = C.tie_out(d)
    assert t["ties"] and t["difference"] == 0 and t["total_submitted"] == 2257
    s = C.bucket_summary(d).set_index("bucket")
    assert s.loc["Paid", "amount"] == 800 and s.loc["Adjustment", "amount"] == 200
    assert s.loc["DQ Hold", "claims"] == 3 and s.loc["DQ Hold", "amount"] == -50 + 100 + 7
    assert s["claims"].drop("Adjustment").sum() == 8 - 1  # one Approved claim sits in Paid; counted once


def test_tie_out_detects_a_broken_classifier():
    d = C.classify(mk(GOOD, ("Denied", "500", "0", "2024-01-01", "2024-02-01", "")))
    d.loc[d["bucket"] == "Denied", "submitted_amount"] = 999  # break the link between detail and total
    assert C.tie_out(d)["ties"]  # amounts are read from the same column, so editing it keeps the tie ...
    d2 = d.copy()
    d2.loc[0, "paid_amount"] = 1  # ... but changing a bucket component must be caught
    assert not C.tie_out(d2)["ties"]


def _decided(n_ok, n_den, pipe):
    rows = [("Approved", "1000", "800", "2024-01-01", "2024-02-01", "2024-03-01")] * n_ok
    rows += [("Denied", "1000", "0", "2024-01-01", "2024-02-01", "")] * n_den
    rows += [("Pending", "1000", "", "2024-01-01", "", "")] * pipe
    return C.classify(mk(*rows))


def test_expected_value_includes_the_denial_rate():
    ev = C.expected_value(_decided(6, 4, 10))
    assert ev["approval_ratio"] == pytest.approx(0.8) and ev["approval_share_dollars"] == pytest.approx(0.6)
    assert ev["pipeline_submitted"] == 10000
    assert ev["expected"] == pytest.approx(10000 * 0.6 * 0.8)
    assert ev["ceiling_no_denials"] == pytest.approx(8000) and ev["expected"] < ev["ceiling_no_denials"]
    assert ev["low"] <= ev["expected"] <= ev["high"]


def test_expected_value_is_reproducible():
    d = _decided(6, 4, 10)
    assert C.expected_value(d) == C.expected_value(d)


def test_expected_value_without_denials_or_data_has_no_range():
    ev = C.expected_value(_decided(3, 0, 5))
    assert ev["low"] is None and ev["expected"] == pytest.approx(ev["ceiling_no_denials"])


def test_pipeline_aging_bands():
    d = C.classify(
        mk(
            ("Pending", "10", "", "2026-10-01", "", ""),  # 20 days
            ("Pending", "20", "", "2026-05-01", "", ""),  # 173 days
            ("Pending", "30", "", "2026-01-01", "", ""),  # 293 days
            ("Pending", "40", "", "2020-01-01", "", ""),  # over a year
            ("Pending", "50", "", "2027-01-01", "", ""),  # future
        )
    ).pipe(C.pipeline_aging)
    got = dict(zip(d["age"], d["claims"], strict=True))
    assert got == {
        "0-90 days": 1,
        "91-180 days": 1,
        "181-365 days": 1,
        "Over 1 year": 1,
        "Submitted date missing or in the future": 1,
    }
    assert d["submitted"].sum() == 150


def test_brief_reconciliation_shows_the_difference():
    r = C.brief_reconciliation(C.classify(mk(GOOD))).set_index("measure")
    assert r.loc["Submitted on approved claims", "data"] == 1000
    assert r.loc["Gap (submitted - received)", "brief"] == 500000


def test_exceptions_list_holds_and_date_flags_separately():
    d = C.classify(
        mk(
            ("Approved", "-5", "1", "2024-01-01", "2024-02-01", "2024-03-01"),
            ("Approved", "1000", "800", "2024-05-01", "2024-02-01", "2024-06-01"),
            GOOD,
        )
    )
    e = C.exceptions(d)
    assert e["treatment"].tolist() == [
        "Held out of all other buckets",
        "Stays in its bucket; date problem only",
    ]


def test_date_flag_effect_counts_flagged_paid_claims():
    d = C.classify(mk(GOOD, ("Approved", "1000", "800", "2024-05-01", "2024-02-01", "2024-06-01")))
    x = C.date_flag_effect(d)
    assert (x["paid_claims"], x["paid_claims_with_date_flag"]) == (2, 1) and x["paid_without_flagged"] == 800
