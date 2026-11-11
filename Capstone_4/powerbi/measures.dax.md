# Power BI measures

Data source: the CSV files in `outputs/powerbi/` (written by `python -m hcls powerbi`, no personal data). Load each file with **Get data > Text/CSV**, then in Power Query set `run_ts` columns to *Date/Time*, money columns to *Fixed decimal number* and ids to *Text*.

## Relationships (Model view)

| From (many) | To (one) | Direction |
|---|---|---|
| `fact_scorecard[severity]` | `dim_severity[severity]` | single |
| `fact_recon_buckets[bucket]` | `dim_bucket[bucket]` | single |
| `fact_claims[bucket]` | `dim_bucket[bucket]` | single |
| `fact_timeline[rule_id]` | `fact_scorecard[rule_id]` | single |

Sort `dim_severity[severity]` by `dim_severity[sort]`, `dim_bucket[bucket]` by `dim_bucket[sort]`, and `fact_waterfall[step]` by `fact_waterfall[sort]`.

## Headline measures (page 1)

```dax
Latest Run = MAX ( fact_metrics[run_ts] )

Metric Latest =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[run_ts] = r )

Critical Rules Failing =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "critical_rules_failing", fact_metrics[run_ts] = r )

Rule Pass Rate =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "rule_pass_rate", fact_metrics[run_ts] = r ) / 100

Paid Certain =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "paid_certain", fact_metrics[run_ts] = r )

Pipeline Estimated =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "pipeline_estimated", fact_metrics[run_ts] = r )

Pipeline Expected =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "pipeline_expected", fact_metrics[run_ts] = r )

Claims On Hold =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "claims_on_dq_hold", fact_metrics[run_ts] = r )

Open Alerts =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "alerts_open", fact_metrics[run_ts] = r )
```

Show **Rule Pass Rate** as a percentage. Do not label **Pipeline Estimated** or **Pipeline Expected** as "revenue"; put "Estimated" in the card title.

## Scorecard (page 2)

```dax
Rules With Findings = CALCULATE ( DISTINCTCOUNT ( fact_scorecard[rule_id] ), fact_scorecard[rows_failed] > 0 )

Rows Failed = SUM ( fact_scorecard[rows_failed] )

Failure Rate = DIVIDE ( SUM ( fact_scorecard[rows_failed] ), SUM ( fact_scorecard[rows_checked] ) )

Impact Score = SUM ( fact_scorecard[impact_score] )
```

## Timeline (page 3)

```dax
Timeline Failure Rate = DIVIDE ( SUM ( fact_timeline[rows_failed] ), SUM ( fact_timeline[rows_checked] ) )

Evidence Of Change =
IF ( MIN ( fact_timeline_tests[p_value] ) < 0.05, "Rate changed over time", "Flat: no evidence of a change" )
```

## Finance (page 4)

```dax
Submitted Total = SUM ( fact_claims[submitted_amount] )

Bucket Amount = SUM ( fact_recon_buckets[amount] )

Certain Amount =
CALCULATE ( SUM ( fact_claims[submitted_amount] ), dim_bucket[confidence_group] = "Certain" )

Estimated Amount =
CALCULATE ( SUM ( fact_claims[submitted_amount] ), dim_bucket[confidence_group] = "Estimated" )

Held Amount =
CALCULATE ( SUM ( fact_claims[submitted_amount] ), dim_bucket[confidence_group] = "Excluded" )

Waterfall Amount = SUM ( fact_waterfall[amount] )

Open Claims Over A Year =
CALCULATE ( COUNTROWS ( fact_claims ), fact_claims[bucket] = "Pipeline", fact_claims[age_days] > 365 )
```

`Certain Amount` uses the submitted dollars per bucket, so it is not the paid total. Use **Paid Certain** for the paid figure. `Bucket Amount` ties to the workbook's summary sheet; the *Adjustment* row is part of the paid claims, so the bucket rows do not add up to `Submitted Total` (the waterfall does).

## Patient care and compliance (page 5)

```dax
Records Without Medication =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "c03_records_without_medication", fact_metrics[run_ts] = r )

Visits Without Appointment =
VAR r = [Latest Run]
RETURN CALCULATE ( SUM ( fact_metrics[value] ), fact_metrics[metric] = "c02_visits_without_appointment", fact_metrics[run_ts] = r )

Broken Links = CALCULATE ( COUNTROWS ( fact_link_health ), fact_link_health[status] = "broken" )

Open Remediation Groups = CALCULATE ( COUNTROWS ( fact_remediation ), fact_remediation[status] = "Open" )

Backfill Applied =
SUM ( fact_backfill[applied_to_copy] )

Refund Status = "On hold: claim-to-bill link is wrong on every claim"
```
