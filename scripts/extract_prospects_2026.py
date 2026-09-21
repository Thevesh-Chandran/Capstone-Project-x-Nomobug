"""Live, read-only Sheets -> DataFrame check. No CSV input or database writes.

Run from the activated project environment:
    python scripts/extract_prospects_2026.py

Read top-to-bottom. df contains displayed source values plus source_sheet_row;
header_map retains exact header text. Only column labels and aggregate counts
are printed; customer values are not printed or saved to disk.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 1. Reuse existing private configuration. Never put IDs or tokens in this file.
project_folder = Path(__file__).resolve().parents[1]
load_dotenv(project_folder / ".env")
paths = {}
for name, default in {
    "NOMOBUG_GOOGLE_TOKEN": "secrets/google_token.json",
    "NOMOBUG_GOOGLE_SOURCE_IDS": "secrets/google_source_ids.json",
    "NOMOBUG_GOOGLE_METADATA": "data/profiles/google_source_metadata.json",
}.items():
    path = Path(os.getenv(name) or default).expanduser()
    paths[name] = path if path.is_absolute() else project_folder / path
    if not paths[name].is_file():
        raise SystemExit(f"Missing local file for {name}. Check its path; do not share its contents.")

try:
    source_config = json.loads(paths["NOMOBUG_GOOGLE_SOURCE_IDS"].read_text(encoding="utf-8-sig"))
    metadata = json.loads(paths["NOMOBUG_GOOGLE_METADATA"].read_text(encoding="utf-8-sig"))
except (ValueError, OSError):
    raise SystemExit("Could not read private source configuration. Check the local JSON files.") from None

workbook_title = "Prospects List - Nomobug"
tab_name = "2026"
matches = [item for item in metadata.get("spreadsheets", [])
           if item.get("properties", {}).get("title") == workbook_title]
if len(matches) != 1:
    raise SystemExit("Expected exactly one Prospects workbook in local metadata. Review the source inventory.")
spreadsheet_id = matches[0].get("spreadsheetId")
if not spreadsheet_id or spreadsheet_id not in source_config.get("spreadsheet_ids", []):
    raise SystemExit("Prospects workbook is not in the approved private source-ID list.")

# 2. Reuse the saved OAuth sign-in; refresh in memory if necessary.
# These are the same read-only scopes used by the existing scripts.
scopes = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
try:
    credentials = Credentials.from_authorized_user_file(str(paths["NOMOBUG_GOOGLE_TOKEN"]), scopes)
    if not credentials.valid:
        if not credentials.refresh_token:
            raise SystemExit("Google sign-in needs renewal. Stop here; do not delete the saved token.")
        credentials.refresh(Request())
except (GoogleAuthError, ValueError, OSError):
    raise SystemExit("Google authentication failed. Sign-in may need renewal; no source rows were loaded.") from None

# 3. Confirm the LIVE workbook/tab, then read the entire tab, not a sample range.
service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
try:
    live_metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="properties(title),sheets(properties(sheetId,title))",
    ).execute(num_retries=2)
    live_tabs = [item["properties"]["title"] for item in live_metadata.get("sheets", [])]
    if live_metadata.get("properties", {}).get("title") != workbook_title or tab_name not in live_tabs:
        raise SystemExit("Live workbook/tab does not match the approved source. Review the source mapping.")

    extraction_started_at = datetime.now(timezone.utc).isoformat()
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="'2026'",
        majorDimension="ROWS",
        valueRenderOption="FORMATTED_VALUE",
    ).execute(num_retries=2)
    extracted_at = datetime.now(timezone.utc).isoformat()
except HttpError as error:
    raise SystemExit(f"Google Sheets request failed (HTTP {error.resp.status}). No data was saved or uploaded.") from None
except (GoogleAuthError, OSError):
    raise SystemExit("Google connection/authentication failed. No data was saved or uploaded.") from None
finally:
    service.close()

# 4. Preserve every API-returned row, including internal blanks and repeat enquiries.
# Google omits trailing empty rows/columns. It returns formula RESULTS here, not formulas.
sheet_rows = response.get("values", [])
if not sheet_rows:
    raise SystemExit("The live tab returned no header/data. Stop before any database load.")
if "NO TELEFON" not in [str(value).strip().upper() for value in sheet_rows[0]]:
    raise SystemExit("Expected NO TELEFON in header row 1. Review the live header before loading.")

width = max(len(row) for row in sheet_rows)
original_headers = sheet_rows[0] + [""] * (width - len(sheet_rows[0]))
# Position-based names cannot collide, even when original headers repeat or are blank.
columns = [f"source_column_{position:03d}" for position in range(1, width + 1)]
header_map = pd.DataFrame({"dataframe_column": columns, "original_header": original_headers})
data_rows = [row + [""] * (width - len(row)) for row in sheet_rows[1:]]
df = pd.DataFrame(data_rows, columns=columns, dtype=str)

# Compute checks BEFORE adding unique lineage, which would hide exact repeats.
blank_rows = df.replace(r"^\s*$", pd.NA, regex=True).isna().all(axis=1)
exact_repeats = int(df.duplicated().sum())
df.insert(0, "source_sheet_row", range(2, len(df) + 2))
assert len(df) == len(sheet_rows) - 1
assert df["source_sheet_row"].is_unique

# 5. Terminal summary only. No phone numbers, source IDs or customer previews.
print("Source: Prospects List - Nomobug / 2026 (LIVE API)")
print("Extraction started UTC:", extraction_started_at)
print("Extraction completed UTC:", extracted_at)
print("API data rows:", len(sheet_rows) - 1)
print("DataFrame rows:", len(df))
print("Source columns:", width)
print("Entirely blank returned rows (retained):", int(blank_rows.sum()))
print("Exact repeated rows beyond first (retained):", exact_repeats)
print("Sheet row numbers retained:", "2 through " + str(len(df) + 1) if len(df) else "No data rows")
print("Row-count check: PASS")
print("No rows removed. No CSV read/written. No Neon upload. Google Sheet unchanged.")

# 6. Inspect column completeness on a separate copy; leave the raw df unchanged.
checked_values = df[columns].replace(r"^\s*$", pd.NA, regex=True)
column_profile = header_map.copy()
column_profile["original_header"] = (
    column_profile["original_header"].astype(str)
    .str.replace(r"\s+", " ", regex=True).str.strip().replace("", "(blank header)")
)
column_profile["filled_cells"] = checked_values.notna().sum().to_numpy()
column_profile["blank_cells"] = checked_values.isna().sum().to_numpy()
column_profile["blank_percent"] = (
    (column_profile["blank_cells"] / len(df) * 100).round(2) if len(df) else pd.NA
)
column_profile["distinct_nonblank"] = checked_values.nunique(dropna=True).to_numpy()
assert ((column_profile["filled_cells"] + column_profile["blank_cells"]) == len(df)).all()

print("\nColumn mapping and completeness (labels/counts only):")
print(column_profile.to_string(index=False))
print("\nBlank means empty or whitespace-only; labels such as N/A or FALSE are not treated as blank.")
print("Distinct counts use displayed values exactly; they are not counts of unique customers.")
print("Blank headers do not imply empty columns. Original header text remains in header_map.")

# 7. Flag possible template rows WITHOUT deleting or changing source values.
# ENGAGE is the manually entered first-reply date, not the incoming-message date.
# The five observed follow-up columns are scheduled dates, not completed contacts.
normalized_headers = (
    header_map["original_header"].astype(str)
    .str.replace(r"\s+", " ", regex=True).str.strip().str.upper()
)
followup_headers = ["1ST F/UP", "2ND F/UP", "3RD F/UP", "4TH F/UP", "5TH F/UP"]
followup_columns = header_map.loc[
    normalized_headers.isin(followup_headers), "dataframe_column"
].tolist()
other_columns = [column for column in columns if column not in followup_columns]
# Phone or first-reply date is a candidate signal, not proof of a unique customer.
signal_columns = header_map.loc[
    normalized_headers.isin(["NO TELEFON", "ENGAGE"]), "dataframe_column"
].tolist()
has_signal = checked_values[signal_columns].notna().any(axis=1)
has_other_values = checked_values[other_columns].notna().any(axis=1)
has_followup = checked_values[followup_columns].notna().any(axis=1)

row_flags = df[["source_sheet_row"]].copy()
row_flags["row_class"] = "blank_returned_row"
row_flags.loc[has_followup & ~has_other_values, "row_class"] = "followup_only_candidate"
row_flags.loc[has_other_values, "row_class"] = "other_values_needs_review"
row_flags.loc[has_signal, "row_class"] = "phone_or_first_reply_present"
row_summary = row_flags["row_class"].value_counts().rename_axis("row_class").reset_index(name="rows")
assert int(row_summary["rows"].sum()) == len(df)
assert row_flags.loc[row_flags["row_class"] == "blank_returned_row"].shape[0] == int(blank_rows.sum())

print("\nProvisional row classification (all rows retained):")
print(row_summary.to_string(index=False))
print("Row-classification count check: PASS")
print("Phone/first-reply presence is not a verified prospect or unique-customer count.")
print("Follow-up-only rows are template candidates pending review, not confirmed duplicates.")
print("No rows removed or uploaded. Automatic dates do not prove follow-up completion.")

# 8. Inspect the review group using presence/counts only, never customer values.
# .loc selects those rows; .notna() turns cells into True/False presence flags.
review_mask = row_flags["row_class"].eq("other_values_needs_review")
review_presence = checked_values.loc[review_mask].notna()
review_profile = column_profile[["dataframe_column", "original_header"]].copy()
review_profile["filled_in_review_rows"] = review_presence.sum().to_numpy()
review_profile = review_profile.loc[review_profile["filled_in_review_rows"] > 0]

# Distinguish a serial number alone from any additional non-follow-up content.
# Blank/unknown headers are included: their contents must not be silently ignored.
number_columns = header_map.loc[normalized_headers.eq("NO"), "dataframe_column"].tolist()
review_detail_columns = [column for column in other_columns if column not in number_columns]
has_review_details = review_presence[review_detail_columns].any(axis=1)
number_only_count = int((review_presence[number_columns].any(axis=1) & ~has_review_details).sum())
other_detail_count = int(has_review_details.sum())
assert number_only_count + other_detail_count == int(review_mask.sum())

print("\nReview-group column check (labels/counts only):")
print("Rows needing review:", int(review_mask.sum()))
if review_profile.empty:
    print("No review rows to inspect.")
else:
    print(review_profile.to_string(index=False))
print("Only No populated outside automatic follow-ups:", number_only_count)
print("Other non-follow-up details present:", other_detail_count)
print("Review-group count check: PASS")
print("Column counts overlap: one row can populate several columns.")
print("Presence does not establish validity. All source rows and values remain unchanged.")
