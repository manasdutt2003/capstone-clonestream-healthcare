# Building `CloneStream_DQ.pbix`

The report file itself is built in Power BI Desktop from this guide; Desktop is a Windows application and a `.pbix` cannot be generated from code. Everything the report needs is generated: the tables (`outputs/powerbi/`), the measures (`measures.dax.md`) and the theme (`theme.json`). Allow about an hour.

## 1. Load the data
1. Run `python -m hcls all` (or `make all`). This writes `outputs/powerbi/*.csv` (18 tables, no personal data).
2. Power BI Desktop > **Get data > Text/CSV**, load every file in `outputs/powerbi/` except `manifest.csv`. (Or **Get data > Folder** and expand.)
3. In Power Query: `run_ts` columns to Date/Time; `*_amount`, `amount`, `submitted` to Fixed decimal; `patient_id`, `claim_id` to Text.
4. Add the four relationships in `measures.dax.md`. Sort the dimension columns as listed there.
5. **View > Themes > Browse for themes** and pick `powerbi/theme.json`.
6. Paste the measures from `measures.dax.md` (New measure).

## 2. Pages

| # | Page | Visuals (table and columns) | Message |
|---|---|---|---|
| 1 | Executive overview | Cards: **Critical Rules Failing**, **Rule Pass Rate**, **Paid Certain**, **Pipeline Expected** (title "Pipeline, estimated"), **Claims On Hold**, **Open Alerts**. 100% stacked bar of `dim_bucket[confidence_group]` by `fact_recon_buckets[amount]`. | What is certain and what is not, on one screen. |
| 2 | DQ scorecard | Matrix: rows `fact_scorecard[table]`, columns `dim_severity[severity]`, values **Rules With Findings**. Heatmap: `check_type` by `table`, values **Failure Rate**, conditional colour. Table of rule, name, rows failed, with **drill-through** from the matrix to rule detail. Slicers: stakeholder, severity. | Where the problems are. |
| 3 | Timeline | Line chart: `fact_timeline[year]`, **Timeline Failure Rate**, legend `rule_id`, default filter C01, C02, C03. Table from `fact_timeline_tests`: rule, p_value, verdict. Card: **Evidence Of Change**. | "Systemic since 2020": the rate does not move. |
| 4 | Finance reconciliation | Waterfall: category `fact_waterfall[step]`, values **Waterfall Amount**. Table: bucket, claims, amount, `dim_bucket[confidence_group]`. Column chart of `fact_pipeline_aging`. Card **Open Claims Over A Year**. Text box with the confidence legend: Certain, Estimated, Excluded. | Submitted dollars down to paid; the estimate is labelled as an estimate. |
| 5 | Patient care and compliance | Cards: **Records Without Medication**, **Visits Without Appointment**, **Broken Links**, **Backfill Applied**, **Refund Status**. Table: `fact_remediation` (group, title, owner, effort, status). Bar: `fact_link_health` by status. | What needs a human, who owns it, and the refund hold. |

Page 1 must say "estimated" wherever it shows a pipeline number. Do not add a card that adds Paid and Pipeline together.

## 3. Check before you share
- On page 4 `Submitted Total` shows $6,066,812.08 and the last bar of the waterfall (Paid) shows $1,945,489, the same as **Paid Certain** on page 1. (The bucket table lists *Adjustment* inside the paid claims, so its rows do not add to the total; the waterfall does.)
- **Critical Rules Failing** equals 5 and **Paid Certain** equals $1,945,489.
- No visual shows a name, e-mail, phone or address. (There are none in the tables; `python -m hcls powerbi` refuses to write one.)

## 4. Refresh
Power BI reads CSV files, so the refresh needs the files to be reachable:
- **Desktop:** run `python -m hcls all`, then **Refresh**.
- **Service (scheduled daily refresh):** the `dq_daily` and `audit_nightly` jobs (`databricks/jobs/`) rebuild the files. Publish them to a location the Power BI Service can read (a SharePoint/OneDrive folder or ADLS) and point the report's data source there; use a gateway if the files stay on-premises. Set the refresh to run after the 02:00 UTC job.

Both the job schedule and the publish location are design only here: no Databricks workspace or Power BI tenant was available (D-001).
