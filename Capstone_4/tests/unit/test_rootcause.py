"""Unit tests for the root-cause tooling: timeline statistics, lineage status and hypothesis verdict logic."""

import copy

import pandas as pd
import pytest

from hcls.rootcause import evidence, lineage, timeline


def series(rows):
    df = pd.DataFrame(rows, columns=["period", "records", "failed"])
    df["rate_pct"] = (df["failed"] / df["records"] * 100).round(1)
    return df


# ------------------------------------------------------------------ timeline


@pytest.mark.parametrize(
    ("value", "period", "expected"),
    [
        ("2023-05-17", "year", "2023"),
        ("2023-05-17", "quarter", "2023-Q2"),
        ("2023-12-01 10:00:00", "quarter", "2023-Q4"),
        ("2023-13-01", "year", None),
        ("tomorrow", "year", None),
        (None, "year", None),
        ("", "year", None),
    ],
)
def test_period_of(value, period, expected):
    assert timeline.period_of(value, period) == expected


def test_failure_series_counts_by_year():
    frame = pd.DataFrame({"_row_num": [2, 3, 4, 5], "d": ["2020-01-01", "2020-06-01", "2021-01-01", "bad"]})
    out = timeline.failure_series(frame, {2, 4}, "d").set_index("period")
    assert out.loc["2020", ["records", "failed"]].tolist() == [2, 1]
    assert out.loc["2021", ["records", "failed"]].tolist() == [1, 1]
    assert len(out) == 2  # the unparseable date is not assigned to a year


def test_flat_rate_is_not_a_break():
    r = timeline.homogeneity_test(series([("2020", 100, 30), ("2021", 100, 31), ("2022", 100, 29)]))
    assert r["verdict"].startswith("flat") and r["p_value"] > 0.05


def test_changing_rate_is_detected():
    r = timeline.homogeneity_test(
        series([("2020", 100, 5), ("2021", 100, 6), ("2022", 100, 60), ("2023", 100, 62)])
    )
    assert r["verdict"] == "rate changes over time" and r["p_value"] < 0.001


def test_all_fail_and_none_fail_are_reported_as_constants():
    assert timeline.homogeneity_test(series([("2020", 50, 50), ("2021", 50, 50)]))["verdict"].startswith(
        "constant"
    )
    assert (
        timeline.homogeneity_test(series([("2020", 50, 0), ("2021", 50, 0)]))["verdict"]
        == "none in any period"
    )


def test_small_periods_are_not_tested():
    r = timeline.homogeneity_test(series([("2020", 3, 3), ("2021", 100, 10)]))
    assert r["verdict"] == "insufficient data" and r["periods_tested"] == 1


def test_best_split_finds_the_change_point_and_adjusts_p():
    s = series([("2020", 100, 5), ("2021", 100, 5), ("2022", 100, 60), ("2023", 100, 60)])
    b = timeline.best_split(s)
    assert b["split_before"] == "2022" and (b["rate_before"], b["rate_after"]) == (5.0, 60.0)
    assert b["p_adjusted"] < 0.001
    flat = timeline.best_split(series([("2020", 100, 30), ("2021", 100, 30), ("2022", 100, 30)]))
    assert flat["p_adjusted"] is None or flat["p_adjusted"] >= 0.05


def test_best_split_with_nothing_to_split():
    assert timeline.best_split(series([("2020", 100, 10)]))["split_before"] is None


# ------------------------------------------------------------------ lineage


@pytest.mark.parametrize(
    ("pct", "status"),
    [
        (0, "healthy"),
        (0.99, "healthy"),
        (1.0, "degraded"),
        (9.9, "degraded"),
        (10.0, "broken"),
        (100, "broken"),
    ],
)
def test_status_thresholds(pct, status):
    assert lineage.status_of(pct) == status


def test_build_lineage_takes_the_worse_of_orphan_and_wrong_patient():
    sc = pd.DataFrame({"rule_id": ["R-Visits-appointment_id"], "pct_failed": [0.0]})
    lh = pd.DataFrame({"link": ["Visits -> Appointments"], "linked_rows": [100], "same_patient": [20]})
    edges = lineage.build_lineage(sc, lh).set_index(["child_table", "child_column"])
    e = edges.loc[("Visits", "appointment_id")]
    assert e["status"] == "broken" and e["wrong_patient_pct"] == 80.0
    other = edges[edges["wrong_patient_pct"].isna()]
    assert (other["status"] == "healthy").all()  # no rule failures supplied, so nothing else is flagged


def test_mermaid_is_valid_flowchart_with_coloured_edges():
    sc = pd.DataFrame({"rule_id": [], "pct_failed": []})
    lh = pd.DataFrame({"link": ["Visits -> Appointments"], "linked_rows": [100], "same_patient": [0]})
    text = lineage.to_mermaid(lineage.build_lineage(sc, lh))
    assert text.startswith("flowchart LR") and "subgraph" in text and "linkStyle" in text
    assert text.count("-->") == 39  # one arrow per foreign key
    assert "#d62728" in text or "stroke" in text


# ------------------------------------------------------------------ hypothesis verdicts


def test_status_groups_cover_every_claim_status():
    assert set(evidence.DECIDED).isdisjoint(evidence.PIPELINE)
    assert set(evidence.DECIDED) | set(evidence.PIPELINE) == {
        "Approved",
        "Denied",
        "Appealed",
        "Submitted",
        "Pending",
        "In Review",
    }


@pytest.mark.realdata
def test_verdicts_change_when_the_evidence_changes(bronze, raw_results):
    """Verdicts are computed: break the evidence and the verdict must move."""
    from hcls.dq import scorecard

    res, tl, fails = raw_results
    ev = evidence.collect(bronze, scorecard.build_scorecard(res.reset_index(), tl), fails)
    base = {h["id"]: h["verdict"] for h in evidence.build_hypotheses(ev)}
    assert base["H1.2"] == "Confirmed"

    broken = copy.deepcopy(ev)
    s = broken["c01_blank_by_status"]
    s.loc[s["claim_status"] == "Approved", "approved_amount_blank"] = 5  # a decided claim now lacks an amount
    changed = {h["id"]: h["verdict"] for h in evidence.build_hypotheses(broken)}
    assert changed["H1.1"] != "Ruled out" and changed["H1.2"] != "Confirmed"
