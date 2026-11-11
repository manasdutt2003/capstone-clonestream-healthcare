"""Write the cleaned workbook (same 20 sheets, real data types) plus a Cleaning_Summary sheet."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from hcls import config
from hcls.standardise import cleaning_summary, infer_kinds, to_typed

HEADER_FILL = PatternFill("solid", fgColor="075056")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def write_clean_workbook(
    silver: dict[str, pd.DataFrame], changes: pd.DataFrame, path: Path | str | None = None
) -> Path:
    path = Path(path) if path else config.path("clean_workbook")
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(
        path, engine="openpyxl", date_format="yyyy-mm-dd", datetime_format="yyyy-mm-dd hh:mm:ss"
    ) as xw:
        for name, df in silver.items():
            typed = to_typed(name, df)
            typed.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            kinds = infer_kinds(name, df)
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for idx, col in enumerate(typed.columns, start=1):
                cell = ws.cell(row=1, column=idx)
                cell.fill, cell.font = HEADER_FILL, HEADER_FONT
                longest = max(
                    [len(str(col))] + [len(str(v)) for v in typed[col].head(200).tolist() if v is not None]
                )
                ws.column_dimensions[get_column_letter(idx)].width = min(max(10, longest + 2), 45)
                if kinds[col] == "date":
                    for r in range(2, ws.max_row + 1):
                        ws.cell(row=r, column=idx).number_format = "yyyy-mm-dd"
        summary = cleaning_summary(changes)
        summary.to_excel(xw, sheet_name="Cleaning_Summary", index=False)
        ws = xw.sheets["Cleaning_Summary"]
        ws.freeze_panes = "A2"
        for idx in range(1, 5):
            cell = ws.cell(row=1, column=idx)
            cell.fill, cell.font = HEADER_FILL, HEADER_FONT
            ws.column_dimensions[get_column_letter(idx)].width = [24, 28, 28, 16][idx - 1]
    return path
