# Finance Brief: claims reconciliation

*As of 2026-10-21. For the CFO and Finance. Detail by claim: `CloneStream_Claims_Reconciliation_2026-10-21.xlsx`. Source: `Insurance_Claims` only.*

## The answer

- **We were paid $1.95M (certain)** on $2.58M of approved claims. The insurers reduced the other **$0.64M**; the reason is not recorded.
- **$2.23M is still being decided** (90 claims, estimated). We expect about **$1.17M** of it to be approved (range $1.04M to $1.30M).
- **$1.12M was denied** (49 claims). The amount is certain; how much can be recovered is not known.
- **$0.16M is under appeal** (estimated, outcome unknown).
- **4 claims are held out** (3 approved, 1 denied) because an amount or payment date is impossible. They need checking at the source.
- **Every dollar is accounted for:** the buckets add up to $6,066,812 submitted across all 250 claims, to the cent.

## What is certain and what is estimated

| Bucket | Claims | Amount | Confidence |
|---|---:|---:|---|
| Paid | 97 | $1,945,489 | Certain |
| Adjustment | 97 | $636,901 | Certain (amount); reason Estimated |
| Denied | 49 | $1,123,431 | Certain (amount); recovery Estimated |
| Under appeal | 10 | $157,484 | Estimated |
| Pipeline | 90 | $2,225,289 | Estimated |
| DQ Hold | 4 | -$21,782 | Excluded: needs review |
| **Total submitted** | **250** | **$6,066,812** | |

## Three things to know before you quote a number

1. **This is lower than the earlier Finance Flash on two points.** The Flash said $2.03M paid; $0.08M of that sits on 3 approved claims with impossible data and is now held. The Flash also said about $1.68M would be approved from the open claims; that assumed nothing is ever denied, so it is the **ceiling**, not the expectation.
2. **The open claims are old.** 78 of the 90 open claims were submitted more than a year ago. Claims waiting that long may never be decided, so treat the $1.17M as optimistic and ask the claims team which are really in flight.
3. **Dates in this data are unreliable** (84 of 97 paid claims have a date out of order). The amounts and statuses are consistent, so the buckets rest on them. Do not use the dates for payment timing; confirm the paid total against the insurer remittance or bank before using it outside the company.

## Were patients over-charged? We cannot say yet

**Recommendation: hold any refund decision.** Why we cannot answer:

- The claim-to-bill link points at a bill for the same patient in 0 of 250 claims.
- A claim's submitted amount is a median 64x the bill it points at; only 1 of 250 are within 25%.
- Only 9 of 250 claim patients have any bill at all, so most claims cannot be matched even by patient.
- Any refund figure built on this link would look precise and be wrong (DECISIONS D-004, D-020).

What we need to answer it:

- The key mapping that links `Insurance_Claims.billing_id` to the bill it was raised for (from the ETL owner), or a corrected extract.
- A re-run of the claim-to-bill link after the key fix, checked first on patient (same patient on both sides).
- The insurer remittance (835) or payment file, to confirm what was actually paid per claim and when.
- A rule from Compliance for what counts as over-charging (patient billed more than the insurer's approved amount, or more than the contracted rate).
- Patient-level payment records (what each patient was actually charged and paid), which this data set does not contain.

## Reconciling to the brief

The brief says submitted $2.30M, received $1.80M, gap $500,000. The data says submitted $2.58M, received $1.95M, gap $636,901. We could not reproduce the brief's figures from any cut of the data we tried (by year, by paid date, with and without the held claims). Use the data's figures.

## How this was produced

`python -m hcls recon` builds the workbook and this brief from the cleaned claims table in about 2.4 seconds (limit: 5 minutes).
Nothing is typed by hand. 125 claims are listed on the `DQ Exceptions` sheet. Method and assumptions: the `Claims Summary` and `Read Me` sheets.
