from pathlib import Path
import pandas as pd

project_folder = Path(__file__).resolve().parents[2]
csv_path = project_folder / "data/raw/prospects/2026.csv"

# Load every CSV record as text, preserving phone numbers and blanks
df = pd.read_csv(
    csv_path,
    dtype=str,
    keep_default_na=False,
    skip_blank_lines=False
)

print("Rows:", len(df))
print("Columns:", len(df.columns))

# Use a separate copy for checking blank cells
# The original df remains unchanged
df_check = df.replace(r"^\s*$", pd.NA, regex=True)

profile = pd.DataFrame({
    "column": df.columns,
    "blank_cells": df_check.isna().sum().to_numpy(),
    "distinct_values": df_check.nunique().to_numpy()
})

# Display multiline headers on one line
profile["column"] = profile["column"].str.replace("\n", " ", regex=False)

print("\nColumn profile:")
print(profile.to_string(index=False))

print("\nExact repeated rows beyond the first:", df.duplicated().sum())
