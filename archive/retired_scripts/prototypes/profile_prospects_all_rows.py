"""Load and profile all populated rows from the two in-scope prospect tabs.

Run locally:
    python scripts/prototypes/profile_prospects_all_rows.py

Raw extracts and profiles are saved only under Git-ignored data folders.
"""

import json
import re
from pathlib import Path

import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


WORKBOOK_TITLE = "Prospects List - Nomobug"

TAB_HEADER_ROWS = {
    "B2B FOLLOW UP": 1,
    "2026": 1,
}

project_root = Path(__file__).resolve().parents[2]
token_path = project_root / "secrets" / "google_token.json"
metadata_path = project_root / "data" / "profiles" / "google_source_metadata.json"
raw_directory = project_root / "data" / "raw" / "prospects"
profile_directory = project_root / "data" / "profiles" / "prospects"

raw_directory.mkdir(parents=True, exist_ok=True)
profile_directory.mkdir(parents=True, exist_ok=True)

scopes = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
sheets_service = build(
    "sheets", "v4", credentials=credentials, cache_discovery=False
)

metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
spreadsheet_id = ""

for workbook in metadata.get("spreadsheets", []):
    if workbook.get("properties", {}).get("title") == WORKBOOK_TITLE:
        spreadsheet_id = workbook.get("spreadsheetId", "")
        break

if not spreadsheet_id:
    raise SystemExit(f"Workbook not found in local metadata: {WORKBOOK_TITLE}")

workbook_summary_rows = []

for tab_name, header_row in TAB_HEADER_ROWS.items():
    escaped_tab_name = tab_name.replace("'", "''")
    response = (
        sheets_service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{escaped_tab_name}'",
            majorDimension="ROWS",
        )
        .execute()
    )

    sheet_rows = response.get("values", [])
    maximum_width = max((len(row) for row in sheet_rows), default=0)

    if maximum_width == 0:
        print(f"{tab_name}: empty tab")
        continue

    if header_row is None:
        header = [f"column_{position + 1}" for position in range(maximum_width)]
        data_rows = sheet_rows
        header_status = "generic_columns_no_reliable_header"
        duplicate_original_headers = []
    else:
        if len(sheet_rows) < header_row:
            print(f"{tab_name}: expected header row {header_row} was not found")
            continue

        original_header = sheet_rows[header_row - 1]
        original_header = original_header + [""] * (
            maximum_width - len(original_header)
        )
        original_header = [
            " ".join(str(column).split())
            if str(column).strip()
            else f"unnamed_{position + 1}"
            for position, column in enumerate(original_header)
        ]

        duplicate_original_headers = pd.Series(original_header)[
            pd.Series(original_header).duplicated()
        ].tolist()

        header_counts = {}
        header = []
        for column in original_header:
            header_counts[column] = header_counts.get(column, 0) + 1
            if header_counts[column] == 1:
                header.append(column)
            else:
                header.append(f"{column}_{header_counts[column]}")

        data_rows = sheet_rows[header_row:]
        header_status = "confirmed_header_row"

    data_rows = [
        (row + [""] * len(header))[:len(header)]
        for row in data_rows
    ]

    df = pd.DataFrame(data_rows, columns=header)
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    df = df.dropna(how="all")

    safe_tab_name = re.sub(r"[^A-Za-z0-9_-]+", "_", tab_name).strip("_")
    raw_path = raw_directory / f"{safe_tab_name}.csv"
    profile_path = profile_directory / f"{safe_tab_name}_column_profile.csv"

    df.to_csv(raw_path, index=False)

    column_profile = pd.DataFrame(
        {
            "column": df.columns,
            "non_null_count": df.notna().sum().to_numpy(),
            "missing_count": df.isna().sum().to_numpy(),
            "missing_percent": (df.isna().mean() * 100).round(2).to_numpy(),
            "distinct_count": df.nunique(dropna=True).to_numpy(),
        }
    )
    column_profile.to_csv(profile_path, index=False)

    workbook_summary_rows.append(
        {
            "tab_name": tab_name,
            "header_row": header_row,
            "header_status": header_status,
            "loaded_rows": len(df),
            "loaded_columns": len(df.columns),
            "exact_duplicate_rows": int(df.duplicated().sum()),
            "duplicate_header_count": len(duplicate_original_headers),
        }
    )

    print(
        f"{tab_name}: rows={len(df):,}, columns={len(df.columns)}, "
        f"exact_duplicates={int(df.duplicated().sum()):,}"
    )

workbook_summary = pd.DataFrame(workbook_summary_rows)
summary_path = profile_directory / "prospects_workbook_summary.csv"
workbook_summary.to_csv(summary_path, index=False)

print("\nSaved raw extracts:", raw_directory)
print("Saved profiles:", profile_directory)
print("Workbook summary:", summary_path)
