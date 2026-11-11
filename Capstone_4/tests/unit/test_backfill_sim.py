"""The backfill simulation fills only unambiguous matches, only on a copy, and proves the source did not change."""

import pandas as pd
import pytest

from hcls.remediation import backfill_sim as B


def mk(**cols):
    n = len(next(iter(cols.values())))
    df = pd.DataFrame(cols)
    df.insert(0, "_row_num", range(2, n + 2))
    return df


def frames(records, rx, visits=None, appts=None):
    base = {
        "Medical_Records": records,
        "Prescriptions": rx,
        "Visits": visits
        if visits is not None
        else mk(visit_id=["1"], patient_id=["1"], appointment_id=["5"], visit_date=["2024-01-01"]),
        "Appointments": appts
        if appts is not None
        else mk(
            appointment_id=["5"],
            patient_id=["1"],
            appointment_date=["2024-01-01T10:00:00"],
            status=["Completed"],
        ),
    }
    return base


def rec(ids, patients, doctors, plans, date="2024-06-01"):
    n = len(ids)
    return mk(
        record_id=ids, patient_id=patients, doctor_id=doctors, treatment_plan=plans,
        prescribed_meds=[None] * n, record_date=[date] * n, appointment_id=["1"] * n,
    )  # fmt: skip


RX = mk(
    prescription_id=["1", "2", "3", "4"],
    patient_id=["1", "2", "3", "4"],
    doctor_id=["10", "10", "10", "10"],
    medication_name=["Aspirin", "Lisinopril", "Insulin", "Metformin"],
    start_date=["2024-01-01", "2024-01-01", "2020-01-01", "2024-01-01"],
    end_date=["", "", "2020-12-31", ""],
)


def test_confidence_levels_for_c03():
    records = rec(
        ["1", "2", "3", "4", "5"],
        ["1", "2", "3", "9", "4"],  # same doctor / other doctor / inactive Rx / no Rx / plan conflict
        ["10", "99", "10", "10", "10"],
        ["Diet", "Diet", "Diet", "Diet", "Lisinopril 10mg"],
    )
    p = B.propose_c03(frames(records, RX)).set_index("record_id")
    assert p.loc["1", "confidence"] == "High" and p.loc["1", "proposed_value"] == "Aspirin"
    assert p.loc["2", "confidence"] == "Medium"
    assert p.loc["3", "confidence"] == "Low" and not p.loc["3", "applied"]
    assert p.loc["4", "confidence"] == "None"
    assert (
        p.loc["5", "confidence"] == "Conflict" and not p.loc["5", "applied"]
    )  # plan names Lisinopril, Rx says Metformin


def test_c03_agreeing_plan_is_still_applied():
    p = B.propose_c03(frames(rec(["1"], ["2"], ["10"], ["Lisinopril 10mg"]), RX))
    assert p.loc[0, "confidence"] == "High" and p.loc[0, "applied"]


def test_c02_matches_one_candidate_only():
    visits = mk(
        visit_id=["1", "2", "3", "4", "5"],
        patient_id=["1", "1", "2", "-1", "7"],
        appointment_id=[None] * 5,
        visit_date=["2024-03-10", "2024-05-01", "2024-03-10", "2024-03-10", "2024-03-10"],
    )
    appts = mk(
        appointment_id=["11", "12", "13", "14", "15"],
        patient_id=["1", "1", "1", "2", "-1"],
        appointment_date=[
            "2024-03-11T09:00:00",
            "2024-03-09T09:00:00",
            "2024-05-01T09:00:00",
            "2024-03-20T09:00:00",
            "2024-03-10T09:00:00",
        ],
        status=["Completed"] * 5,
    )
    p = B.propose_c02(frames(rec(["1"], ["1"], ["10"], ["x"]), RX, visits, appts)).set_index("visit_id")
    assert (
        p.loc["1", "confidence"] == "Ambiguous" and not p.loc["1", "applied"]
    )  # two appointments within a day
    assert p.loc["2", "confidence"] == "High" and p.loc["2", "proposed_appointment_id"] == "13"
    assert p.loc["3", "confidence"] == "None"  # appointment is ten days away
    assert p.loc["4", "confidence"].startswith("Not matchable") and p.loc["5", "confidence"] == "None"


@pytest.mark.realdata
def test_simulation_changes_only_the_copy(cleaned):
    real = cleaned[0]
    before = B.fingerprint(real)
    out = B.simulate(real)
    assert B.fingerprint(real) == before  # the frames we passed in are untouched
    assert out["summary"]["source_unchanged"].all()
    assert out["copy"] is not real and out["copy"]["Medical_Records"] is not real["Medical_Records"]
    assert (out["summary"]["records_failing_after"] <= out["summary"]["records_failing_before"]).all()


def test_fingerprint_detects_any_change():
    f = frames(rec(["1"], ["1"], ["10"], ["Diet"]), RX)
    before = B.fingerprint(f)
    f["Medical_Records"].loc[0, "prescribed_meds"] = "Aspirin"
    assert B.fingerprint(f) != before


@pytest.mark.realdata
def test_real_data_backfill_recovers_nothing_automatically(cleaned):
    out = B.simulate(cleaned[0])
    s = out["summary"].set_index("rule_id")
    assert (
        s.loc["C03", "records_failing_before"],
        s.loc["C03", "applied_to_copy"],
        s.loc["C03", "records_failing_after"],
    ) == (40, 0, 40)
    assert (s.loc["C02", "records_failing_before"], s.loc["C02", "applied_to_copy"]) == (123, 0)
    assert (
        s.loc["C03", "conflicts_with_plan"] == 2
        and s.loc["C03", "proposals_low_or_ambiguous"] == 1
        and s.loc["C03", "no_match"] == 37
    )


@pytest.mark.realdata
def test_simulation_is_deterministic(cleaned):
    a, b = B.simulate(cleaned[0]), B.simulate(cleaned[0])
    pd.testing.assert_frame_equal(a["summary"], b["summary"])
    pd.testing.assert_frame_equal(a["c03"], b["c03"])
