"""When did it start? (Phase 2, task 2.1)

For each Critical rule, compute the failure rate by year and quarter and test whether the rate is *flat* (a design gap
that has always been there) or *shifts* at some point (a break introduced by a change). Pure statistics on the rule results;
no extra data is read.
"""

from __future__ import annotations

import pandas as pd
from scipy.stats import chi2_contingency

# rule -> (table, date column used to place each record in time)
CRITICAL_TIMELINES: dict[str, tuple[str, str]] = {
    "C01": ("Insurance_Claims", "submitted_date"),
    "C02": ("Visits", "visit_date"),
    "C03": ("Medical_Records", "record_date"),
    "A02": ("Insurance_Claims", "submitted_date"),
    "A30": ("Prescription_Administration", "administered_datetime"),
}
MIN_N = 10  # a period needs at least this many records to be tested
ALPHA = 0.05


def period_of(value: str | None, period: str = "year") -> str | None:
    if (
        not isinstance(value, str)
        or len(value) < 7
        or not value[:4].isdigit()
        or value[4] != "-"
        or not value[5:7].isdigit()
    ):
        return None
    year, month = value[:4], int(value[5:7])
    if not 1 <= month <= 12:
        return None
    return year if period == "year" else f"{year}-Q{(month - 1) // 3 + 1}"


def failure_series(
    frame: pd.DataFrame, failed_rows: set[int], date_col: str, period: str = "year"
) -> pd.DataFrame:
    """Records, failures and failure rate per period."""
    df = pd.DataFrame(
        {
            "period": [period_of(v, period) for v in frame[date_col]],
            "failed": [int(r) in failed_rows for r in frame["_row_num"]],
        }
    ).dropna(subset=["period"])
    out = df.groupby("period")["failed"].agg(records="size", failed="sum").reset_index()
    out["rate_pct"] = (out["failed"] / out["records"] * 100).round(1)
    return out


def homogeneity_test(series: pd.DataFrame, min_n: int = MIN_N) -> dict:
    """Chi-square test that every period has the same failure rate."""
    s = series[series["records"] >= min_n]
    if len(s) < 2:
        return {"periods_tested": len(s), "chi2": None, "p_value": None, "verdict": "insufficient data"}
    table = [[int(r.failed), int(r.records - r.failed)] for r in s.itertuples()]
    if all(row[0] == 0 for row in table):
        return {"periods_tested": len(s), "chi2": 0.0, "p_value": 1.0, "verdict": "none in any period"}
    if all(row[1] == 0 for row in table):
        return {
            "periods_tested": len(s),
            "chi2": 0.0,
            "p_value": 1.0,
            "verdict": "constant: every record fails",
        }
    chi2, p, _, _ = chi2_contingency(table, correction=False)
    return {
        "periods_tested": len(s),
        "chi2": round(float(chi2), 2),
        "p_value": round(float(p), 4),
        "verdict": "flat (no evidence of a break)" if p >= ALPHA else "rate changes over time",
    }


def best_split(series: pd.DataFrame, min_n: int = MIN_N) -> dict:
    """The single before / after split with the biggest rate difference, with a Bonferroni-adjusted p-value."""
    s = series[series["records"] >= min_n].sort_values("period").reset_index(drop=True)
    best = None
    splits = 0
    for k in range(1, len(s)):
        a, b = s.iloc[:k], s.iloc[k:]
        fa, na, fb, nb = int(a.failed.sum()), int(a.records.sum()), int(b.failed.sum()), int(b.records.sum())
        if min(na, nb) < min_n or (fa + fb) in (0, na + nb):
            continue
        splits += 1
        _, p, _, _ = chi2_contingency([[fa, na - fa], [fb, nb - fb]], correction=False)
        if best is None or p < best["p"]:
            best = {
                "split_before": s.iloc[k]["period"],
                "rate_before": round(100 * fa / na, 1),
                "rate_after": round(100 * fb / nb, 1),
                "p": float(p),
            }
    if best is None:
        return {"split_before": None, "rate_before": None, "rate_after": None, "p_adjusted": None}
    best["p_adjusted"] = round(min(1.0, best.pop("p") * splits), 4)
    return best


def timeline_report(
    frames: dict[str, pd.DataFrame], failures: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(summary per rule, long table of rates per rule and period)."""
    summary, long = [], []
    for rule, (table, date_col) in CRITICAL_TIMELINES.items():
        rows = set(failures.loc[failures["rule_id"] == rule, "row_num"].astype(int))
        yearly = failure_series(frames[table], rows, date_col, "year")
        quarterly = failure_series(frames[table], rows, date_col, "quarter")
        for per, df in (("year", yearly), ("quarter", quarterly)):
            for r in df.itertuples():
                long.append(
                    {
                        "rule_id": rule,
                        "table": table,
                        "granularity": per,
                        "period": r.period,
                        "records": int(r.records),
                        "failed": int(r.failed),
                        "rate_pct": r.rate_pct,
                    }
                )
        h = homogeneity_test(yearly)
        s = best_split(yearly)
        affected = yearly[yearly["failed"] > 0]
        summary.append(
            {
                "rule_id": rule,
                "table": table,
                "records": int(yearly["records"].sum()),
                "failed": int(yearly["failed"].sum()),
                "overall_rate_pct": round(100 * yearly["failed"].sum() / max(1, yearly["records"].sum()), 1),
                "years_observed": len(yearly),
                "years_with_failures": len(affected),
                "first_year": affected["period"].min() if len(affected) else None,
                "last_year": affected["period"].max() if len(affected) else None,
                "years_tested": h["periods_tested"],
                "chi2": h["chi2"],
                "p_value": h["p_value"],
                "verdict": h["verdict"],
                "best_split_before": s["split_before"],
                "rate_before_pct": s["rate_before"],
                "rate_after_pct": s["rate_after"],
                "split_p_adjusted": s["p_adjusted"],
            }
        )
    return pd.DataFrame(summary), pd.DataFrame(long)
