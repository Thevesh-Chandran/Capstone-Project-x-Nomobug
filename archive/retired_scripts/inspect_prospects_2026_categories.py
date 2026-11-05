"""Review category labels in the latest Prospects 2026 Bronze snapshot.

Read-only: no Google call, database write, or customer-level output.
"""
import contextlib
import io
import runpy
from pathlib import Path

import pandas as pd


# 1. Reuse the checked Bronze-to-pandas reconstruction.
project_folder = Path(__file__).resolve().parents[1]
hidden_preview_output = io.StringIO()
with contextlib.redirect_stdout(hidden_preview_output):
    preview = runpy.run_path(str(project_folder / "scripts/preview_prospects_2026_silver.py"))

candidate_df = preview["candidate_df"]
header_map = preview["header_map"]
headers = preview["headers"]


# 2. Inspect business categories only. Phones and remarks are excluded.
selected_headers = [
    "PLATFORM (ADS / WEBSITE)",
    "RESIDENTIAL/BUSINESS",
    "GPC / ANAI ANAI",
    "STATUS OPEN / CLOSED",
    "PIC",
]

print("Prospects 2026 category inspection (read-only BigQuery snapshot)")
print("Candidate rows:", len(candidate_df))
print("Source values unchanged. No customer-level fields printed.\n")

for selected_header in selected_headers:
    matching = header_map.loc[headers.eq(selected_header), "dataframe_column"]
    if len(matching) != 1:
        raise SystemExit(f"Expected exactly one source column: {selected_header}")

    column = matching.iloc[0]
    values = candidate_df[column].astype("string")
    stripped = values.str.strip()
    comparison = stripped.str.replace(r"\s+", " ", regex=True).str.casefold()
    nonblank = stripped.ne("") & stripped.notna()

    grouped = pd.DataFrame({
        "source_label": values[nonblank],
        "comparison_label": comparison[nonblank],
    })
    counts = (
        grouped.groupby(["comparison_label", "source_label"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(
            ["comparison_label", "rows", "source_label"],
            ascending=[True, False, True],
        )
    )

    print("=" * 72)
    print(selected_header)
    print("Filled rows:", int(nonblank.sum()))
    print("Blank rows:", int((~nonblank).sum()))
    print("Raw labels:", int(values[nonblank].nunique()))
    print("Labels after case/whitespace comparison:", int(comparison[nonblank].nunique()))
    if counts.empty:
        print("No populated labels.")
    else:
        print(counts.to_string(index=False))

print("\nComparison labels are suggestions for review, not approved Silver mappings.")
print("No data changed and no Silver table was written.")
