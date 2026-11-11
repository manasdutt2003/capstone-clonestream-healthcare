"""The remediation matrix covers every Critical and High finding and points only at real validators."""

import pandas as pd
import pytest

from hcls.remediation import plan, validators


def test_matrix_groups_are_complete_and_distinct():
    ids = [g["id"] for g in plan.MATRIX]
    assert len(ids) == len(set(ids))
    for g in plan.MATRIX:
        for key in ("title", "rules", "action", "what", "owner", "effort", "risk", "rollback", "prevent"):
            assert g[key], (g["id"], key)
        assert g["effort"] in {"S", "M", "L"} and g["risk"] in {"Low", "Medium", "High"}


def test_a_rule_belongs_to_exactly_one_group():
    seen: dict[str, str] = {}
    for g in plan.MATRIX:
        for r in g["rules"]:
            assert r not in seen, f"{r} is in {seen[r]} and {g['id']}"
            seen[r] = g["id"]


def test_every_prevention_check_exists():
    known = {c.id for c in validators.CHECKS}
    for g in plan.MATRIX:
        assert set(g["prevent"]) <= known, (g["id"], set(g["prevent"]) - known)


def test_uncovered_finds_a_new_critical_rule():
    sc = pd.DataFrame(
        {
            "rule_id": ["C01", "NEW-1", "LOW-1", "A12"],
            "severity": ["Critical", "High", "Low", "High"],
            "rows_failed": [1, 3, 9, 0],
        }
    )
    assert plan.uncovered(sc) == ["NEW-1"]  # Low severity and zero-failure rules need no plan


@pytest.mark.realdata
def test_every_critical_and_high_finding_has_a_plan(bronze):
    from hcls.dq import runner, scorecard

    res, tl, _ = runner.run_rules(bronze)
    card = scorecard.build_scorecard(res, tl)
    assert plan.uncovered(card) == []
    hi = card[card["severity"].isin(["Critical", "High"]) & (card["rows_failed"] > 0)]
    assert len(hi) == 28


@pytest.mark.realdata
def test_plan_document_renders_every_section(cleaned, raw_results):
    from hcls.dq import scorecard
    from hcls.remediation import backfill_sim

    res, tl, _ = raw_results
    card = scorecard.build_scorecard(res.reset_index(), tl)
    silver = cleaned[0]
    viol = validators.validate(silver)
    text = plan.render_plan(
        card,
        backfill_sim.simulate(silver)["summary"],
        validators.catch_report(silver, viol),
        viol,
        {"status": "ALERT", "alerts": [], "counts": {}},
        "test",
    )
    for needle in (
        "## 1.",
        "## 2.",
        "## 3.",
        "## 4.",
        "## 5.",
        "## 6.",
        "## 7.",
        "## 8.",
        "Sign-off" if False else "sign-off",
        "[ ] Staging evidence",
    ):
        assert needle in text, needle
    assert "NOT COVERED" not in text and "0 of 40" in text and "0 of 123" in text
