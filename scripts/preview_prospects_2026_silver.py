"""Read-only Bronze -> pandas Silver preview. No Google calls or database writes.

Read top-to-bottom. Raw values remain in df; derived flags live in preview_df.
Only aggregate counts and extraction time are printed, never customer values.
"""
import os
import runpy
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

# 1. Reuse the private connection setting.
project_folder = Path(__file__).resolve().parents[1]
load_dotenv(project_folder / ".env")
database_url = os.getenv("DATABASE_URL")
warehouse = os.getenv("NOMOBUG_WAREHOUSE", "bigquery").strip().lower()
if warehouse not in ["bigquery", "neon"]:
    raise SystemExit("NOMOBUG_WAREHOUSE must be bigquery or neon. No automatic fallback.")
if warehouse == "neon" and not database_url:
    raise SystemExit("DATABASE_URL is missing from the repository .env file.")

engine = None
try:
    if warehouse == "bigquery":
        source = runpy.run_path(str(project_folder / "scripts/read_prospects_2026_bigquery.py"))
        batch, stored_df = source["batch"], source["stored_df"]
    else:
        # Existing Neon path is preserved for an explicit manual fallback.
        engine = create_engine(
            make_url(database_url).set(drivername="postgresql+psycopg"),
            connect_args={"connect_timeout": 30, "sslmode": "require"},
        )
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                connection.execute(text("SET LOCAL statement_timeout = '30s'"))
                # Latest STORED extraction, not a claim about current live Sheets data.
                batch_df = pd.read_sql(text("""
                    SELECT snapshot_id, extracted_at, source_row_count,
                           source_column_count, header_map
                    FROM bronze.prospects_2026_batches
                    WHERE source_tab = '2026'
                    ORDER BY extracted_at DESC, snapshot_id DESC LIMIT 1
                """), connection)
                if batch_df.empty:
                    raise SystemExit("No stored 2026 snapshot found. Run the Bronze loader first.")
                batch = batch_df.iloc[0]
                stored_df = pd.read_sql(text("""
                    SELECT source_sheet_row, raw_values
                    FROM bronze.prospects_2026_rows WHERE snapshot_id = :snapshot_id
                    ORDER BY source_sheet_row
                """), connection, params={"snapshot_id": batch["snapshot_id"]})
except (SQLAlchemyError, ValueError):
    raise SystemExit("Bronze read failed. No data changed. Check the connection and tables; do not share credentials.") from None
finally:
    if engine is not None:
        engine.dispose()

# 2. Reconstruct every source column, including unnamed or duplicate headers.
header_map = pd.DataFrame(batch["header_map"])
columns = header_map["dataframe_column"].tolist()
raw_rows = stored_df["raw_values"].tolist()
if (len(raw_rows) != batch["source_row_count"]
        or len(columns) != batch["source_column_count"]
        or len(set(columns)) != len(columns)
        or stored_df["source_sheet_row"].tolist() != list(range(2, len(raw_rows) + 2))
        or any(not isinstance(row, list) or len(row) != len(columns) for row in raw_rows)):
    raise SystemExit("Stored snapshot shape/lineage check failed. Stop before Silver conversion.")
df = pd.DataFrame(raw_rows, columns=columns, dtype=str)
df.insert(0, "source_sheet_row", stored_df["source_sheet_row"].to_numpy())
headers = header_map["original_header"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip().str.upper()
# Do not silently use the wrong column if the source schema changes.
for required in ["NO TELEFON", "ENGAGE", "NO", "1ST F/UP", "2ND F/UP", "3RD F/UP", "4TH F/UP", "5TH F/UP"]:
    if int(headers.eq(required).sum()) != 1:
        raise SystemExit("Expected source headers missing or duplicated. Review header mapping before Silver.")
phone_column = header_map.loc[headers.eq("NO TELEFON"), "dataframe_column"].iloc[0]
engage_column = header_map.loc[headers.eq("ENGAGE"), "dataframe_column"].iloc[0]
number_column = header_map.loc[headers.eq("NO"), "dataframe_column"].iloc[0]
followup_columns = header_map.loc[headers.isin([
    "1ST F/UP", "2ND F/UP", "3RD F/UP", "4TH F/UP", "5TH F/UP"
]), "dataframe_column"].tolist()

# 3. Presence flags: no deduplication, phone normalisation or row deletion.
present = df[columns].replace(r"^\s*$", pd.NA, regex=True).notna()
other_columns = [column for column in columns if column not in followup_columns]
detail_columns = [column for column in other_columns if column != number_column]
has_details = present[detail_columns].any(axis=1)
has_signal = present[[phone_column, engage_column]].any(axis=1)
preview_df = df[["source_sheet_row"]].copy()
preview_df["row_class"] = "blank_returned_row"
preview_df.loc[present[followup_columns].any(axis=1), "row_class"] = "followup_only_placeholder"
preview_df.loc[present[number_column] & ~has_details, "row_class"] = "numbered_only_placeholder"
preview_df.loc[has_details, "row_class"] = "other_values_needs_review"
preview_df.loc[has_signal, "row_class"] = "prospect_candidate"
preview_df["is_placeholder"] = preview_df["row_class"].isin([
    "followup_only_placeholder", "numbered_only_placeholder"
])

# 4. Inspect ENGAGE text SHAPES only. Matching a shape does not prove a valid date.
# Do not infer a year from the tab name or guess day/month order yet.
engage = df[engage_column].astype("string").str.strip()
preview_df["first_reply_format"] = "unrecognised_needs_review"
preview_df.loc[engage.eq(""), "first_reply_format"] = "blank"
patterns = {
    "day_named_month_no_year": r"\d{1,2}[\s/-]+[A-Za-z]+",
    "day_named_month_with_year": r"\d{1,2}[\s/-]+[A-Za-z]+[\s/-]+\d{4}",
    "iso_year_month_day_shape": r"\d{4}-\d{2}-\d{2}",
    "numeric_day_month_order_unconfirmed": r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}",
    "numeric_no_year_order_unconfirmed": r"\d{1,2}[/.-]\d{1,2}",
}
for label, pattern in patterns.items():
    preview_df.loc[engage.str.fullmatch(pattern, na=False), "first_reply_format"] = label

# 5. Count all classifications, then report candidate date shapes separately.
row_summary = preview_df["row_class"].value_counts().rename_axis("row_class").reset_index(name="rows")
date_summary = (
    preview_df.loc[preview_df["row_class"].eq("prospect_candidate"), "first_reply_format"]
    .value_counts().rename_axis("first_reply_format").reset_index(name="rows")
)
assert int(row_summary["rows"].sum()) == len(df)
print("Silver preview (read-only; stored Bronze data):")
print("Warehouse:", warehouse)
print("Snapshot extracted UTC:", pd.to_datetime(batch["extracted_at"], utc=True))
print("Reconstructed rows:", len(df))
print("Source columns:", len(columns))
print("Row/column/lineage check: PASS")
print(row_summary.to_string(index=False))
print("\nENGAGE format counts within prospect candidates:")
print(date_summary.to_string(index=False))
print("Format shapes are NOT validated dates. No year or day/month order assumed.")
print("Prospect candidates are not unique customers; repeat conversations remain separate.")
print("All raw values retained. No customer values printed. No Silver tables written.")

# 6. Profile ALL columns within prospect candidates (not the template rows).
# A loop avoids writing the same pandas checks 24 times. It does not modify df.
candidate_mask = preview_df["row_class"].eq("prospect_candidate")
candidate_df = df.loc[candidate_mask, columns].copy()
profile_records = []
for column, original_header in zip(columns, header_map["original_header"]):
    values = candidate_df[column].astype("string")
    stripped = values.str.strip()
    nonblank = stripped.ne("") & stripped.notna()
    # Comparison only: collapse whitespace/case, without replacing source values.
    comparison = stripped.str.replace(r"\s+", " ", regex=True).str.casefold()
    profile_records.append({
        "column": column,
        "header": " ".join(str(original_header).split()) or "(blank header)",
        "filled": int(nonblank.sum()),
        "blank": int((~nonblank).sum()),
        "blank_pct": round(float((~nonblank).mean()) * 100, 2) if len(values) else None,
        "distinct_raw": int(values[nonblank].nunique()),
        "distinct_comparison": int(comparison[nonblank].nunique()),
        "outer_whitespace": int((values.ne(stripped) & nonblank).sum()),
        "sentinel_like": int(comparison.isin(["n/a", "na", "null", "none", "-", "unknown"]).sum()),
    })
field_profile = pd.DataFrame(profile_records)
assert (field_profile["filled"] + field_profile["blank"]).eq(len(candidate_df)).all()

# 7. Phone STRUCTURES, not phone validation or customer identity resolution.
phones = candidate_df[phone_column].astype("string").str.strip()
phone_shapes = pd.Series("other_needs_review", index=phones.index, dtype="string")
phone_shapes.loc[phones.eq("")] = "blank"
phone_shapes.loc[phones.str.fullmatch(r"[0-9]+", na=False)] = "digits_only"
phone_shapes.loc[phones.str.fullmatch(r"\+[0-9]+", na=False)] = "plus_then_digits"
formatted_phone = phones.str.fullmatch(r"\+?[0-9 ()-]+", na=False) & phones.str.contains(r"[0-9]", na=False)
phone_shapes.loc[formatted_phone & phones.str.contains(r"[ ()-]", na=False)] = "spaces_brackets_or_hyphens"
phone_summary = phone_shapes.value_counts().rename_axis("phone_structure").reset_index(name="rows")
assert int(phone_summary["rows"].sum()) == len(candidate_df)
nonblank_phones = phones[phones.ne("") & phones.notna()]
repeat_phone_rows = int(nonblank_phones.duplicated(keep=False).sum())
repeat_phone_values = int(nonblank_phones[nonblank_phones.duplicated(keep=False)].nunique())

print("\nAll-column profile within prospect candidates:")
print("Denominator (candidate rows):", len(candidate_df))
print(field_profile.to_string(index=False))
print("distinct_comparison ignores case and repeated/outer whitespace; it is NOT an approved category mapping.")
print("sentinel_like counts possible missing-value labels; these are still retained as source values.")
print("Auto-filled follow-up dates do not establish completed contacts, even when fully populated.")
print("\nPhone structure check within prospect candidates:")
print(phone_summary.to_string(index=False))
print("Rows sharing a nonblank phone (outer spaces ignored):", repeat_phone_rows)
print("Distinct repeated phone values (outer spaces ignored):", repeat_phone_values)
print("Phone structures are not validity checks. No country codes inferred or conversations merged.")
print("All-column/phone count checks: PASS")
print("Raw data unchanged. No Silver writes or customer-value output.")
