"""Read LIVE Sheets, then preserve a complete raw snapshot in Neon.

Run with --upload to explicitly allow database writes. No CSV intermediates.
Read top-to-bottom; the existing extractor supplies df and header_map.
"""

import argparse
import hashlib
import json
import os
import runpy
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

# 1. Require an explicit upload flag before reading any source or connecting.
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--upload", action="store_true")
args = parser.parse_args()
if not args.upload:
    raise SystemExit("No upload performed. Run with --upload when ready to write to Neon.")

project_folder = Path(__file__).resolve().parents[2]
load_dotenv(project_folder / ".env")
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL is missing. Check the private repository .env file.")
# Accept the SQLAlchemy-style URL too; psycopg uses the plain PostgreSQL scheme.
database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

# 2. Reuse the tested extractor, including its row-count and source checks.
print("Extraction phase first; Neon upload starts only after its checks pass.")
source = runpy.run_path(str(project_folder / "scripts" / "extract_prospects_2026.py"))
df = source["df"]
columns = source["columns"]
header_map = source["header_map"]
if df.empty:
    raise SystemExit("Empty extraction: no database upload. Investigate the source first.")

# 3. Fingerprint the entire ordered snapshot, NOT individual customers.
# Timestamps are excluded so rerunning identical content cannot duplicate a batch.
# Repeated rows are still retained at their separate source row positions.
raw_rows = df[columns].values.tolist()
snapshot = {
    "format_version": 1,
    "spreadsheet_id": source["spreadsheet_id"],
    "tab": source["tab_name"],
    "headers": header_map.to_dict(orient="records"),
    "rows": raw_rows,
}
snapshot_id = hashlib.sha256(
    json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
).hexdigest()

# 4. One transaction: tables, batch metadata, rows and verification succeed together.
# These private raw tables must never be exposed to dashboard/public roles.
try:
    with psycopg.connect(database_url, connect_timeout=30, sslmode="require") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '120s'")
            cursor.execute("SET LOCAL lock_timeout = '15s'")
            # Serialize this loader, including first-run table creation.
            cursor.execute("SELECT pg_advisory_xact_lock(20260903, 2026)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bronze.prospects_2026_batches (
                    snapshot_id text PRIMARY KEY,
                    source_spreadsheet_id text NOT NULL,
                    source_tab text NOT NULL,
                    extraction_started_at timestamptz NOT NULL,
                    extracted_at timestamptz NOT NULL,
                    loaded_at timestamptz NOT NULL DEFAULT now(),
                    source_row_count integer NOT NULL CHECK (source_row_count > 0),
                    source_column_count integer NOT NULL CHECK (source_column_count > 0),
                    header_map jsonb NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bronze.prospects_2026_rows (
                    snapshot_id text NOT NULL REFERENCES bronze.prospects_2026_batches(snapshot_id),
                    source_sheet_row integer NOT NULL CHECK (source_sheet_row >= 2),
                    raw_values jsonb NOT NULL CHECK (jsonb_typeof(raw_values) = 'array'),
                    PRIMARY KEY (snapshot_id, source_sheet_row)
                )
            """)
            cursor.execute("REVOKE ALL ON bronze.prospects_2026_batches, bronze.prospects_2026_rows FROM PUBLIC")
            cursor.execute("""
                INSERT INTO bronze.prospects_2026_batches
                    (snapshot_id, source_spreadsheet_id, source_tab, extraction_started_at,
                     extracted_at, source_row_count, source_column_count, header_map)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_id) DO NOTHING RETURNING snapshot_id
            """, (snapshot_id, source["spreadsheet_id"], source["tab_name"],
                  source["extraction_started_at"], source["extracted_at"], len(df), len(columns),
                  Jsonb(snapshot["headers"])))
            new_snapshot = cursor.fetchone() is not None
            if new_snapshot:
                # Small batches keep memory/network use manageable; no df.to_sql replace.
                for start in range(0, len(raw_rows), 1000):
                    cursor.executemany("""
                        INSERT INTO bronze.prospects_2026_rows
                            (snapshot_id, source_sheet_row, raw_values) VALUES (%s, %s, %s)
                    """, [(snapshot_id, position + 2, Jsonb(raw_rows[position]))
                          for position in range(start, min(start + 1000, len(raw_rows)))])

            # Compare all stored values and positions, not merely the total count.
            cursor.execute("""
                SELECT source_sheet_row, raw_values FROM bronze.prospects_2026_rows
                WHERE snapshot_id = %s ORDER BY source_sheet_row
            """, (snapshot_id,))
            stored_rows = cursor.fetchall()
            if stored_rows != [(position + 2, values) for position, values in enumerate(raw_rows)]:
                raise ValueError("Stored snapshot failed verification")
    # Exiting the connection block commits only after verification passes.
except (psycopg.Error, ValueError):
    raise SystemExit(
        "Bronze load failed or could not be confirmed. No success is claimed. "
        "Do not share credentials or raw error output. The same command is safe to retry; "
        "an already committed identical snapshot will be checked and skipped."
    ) from None

print("\nBronze load verification:")
print("Status:", "New snapshot committed" if new_snapshot else "Identical snapshot already stored; checked and skipped")
print("API/DataFrame rows:", len(df))
print("Stored rows in this snapshot:", len(stored_rows))
print("Exact row positions and values: PASS")
print("All placeholder and repeated rows retained. Google Sheet unchanged.")
print("Changed source content creates another full snapshot; monitor Neon storage before scheduling.")
