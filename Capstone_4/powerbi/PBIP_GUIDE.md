# Generate the Power BI report with code

A `.pbix` is a binary that only Power BI Desktop writes. A **Power BI Project (`.pbip`)** is the same report as plain text files, which Desktop opens and which code can generate. This is the route used here.

## Run it

```powershell
# from the Capstone 3 folder, venv active
python -m hcls all                 # only if outputs\powerbi has no CSVs
python powerbi\build_pbip.py       # writes powerbi\pbip\CloneStream_DQ.pbip
```

Then in Power BI Desktop: **File > Open report > Browse** and pick `powerbi\pbip\CloneStream_DQ.pbip`.

First-time Desktop setting: **File > Options > Preview features**, turn on **Power BI Project (.pbip) save option** and **Store reports using enhanced metadata format (PBIR)**, then restart Desktop.

What you get: 18 tables loaded from the CSVs, 4 relationships, 30 measures (28 from `measures.dax.md` plus 2 helpers), the CloneStream theme, and 5 pages (Executive overview, DQ scorecard, Timeline, Finance reconciliation, Patient care and compliance), 32 visuals.

## After it opens

1. If Desktop asks for a data source, the folder path is the model parameter `CsvFolder` (Home > Transform data > Manage parameters). It is pre-filled with the absolute path of `outputs\powerbi` on the machine that ran the script.
2. Click **Refresh**. Check the numbers: Critical Rules Failing 5, Paid (certain) $1,945,489, Total submitted $6,066,812, last waterfall bar $1,945,489.
3. **File > Save as** `CloneStream_DQ.pbix` if you want a single file to share.
4. Polish by hand in Desktop (conditional colour on the failure-rate matrix, the confidence legend). Re-running the script overwrites `powerbi\pbip`, so either finish by hand after your last run or change `build_pbip.py`.

## If Desktop will not open it

I could validate every JSON file against Microsoft's published schemas (0 errors), but I could not open it in Desktop. Try, in order:

1. `python powerbi\build_pbip.py --no-theme` (removes the theme registration).
2. Send the exact error text. The fix goes in `build_pbip.py`, never in the generated files.
3. Fallback: the manual route in `BUILD_GUIDE.md` (about an hour) always works.

## Check the files against Microsoft's schemas (optional)

```powershell
git clone --depth 1 --filter=blob:none --sparse https://github.com/microsoft/json-schemas.git ..\_json-schemas
git -C ..\_json-schemas sparse-checkout set fabric/item
python powerbi\build_pbip.py --schemas ..\_json-schemas
```

## Refresh later

Power BI reads the CSVs. After `python -m hcls all`, press **Refresh** in Desktop.
