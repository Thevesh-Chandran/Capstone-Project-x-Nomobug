"""Read-only storage and Bronze snapshot check; no Google API calls."""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

# 1. Read the private connection setting without printing it.
project_folder = Path(__file__).resolve().parents[2]
load_dotenv(project_folder / ".env")
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL is missing from the repository .env file.")

engine = None
try:
    connection_url = make_url(database_url).set(drivername="postgresql+psycopg")
    engine = create_engine(connection_url, connect_args={"connect_timeout": 30, "sslmode": "require"})
    with engine.connect() as connection:
        with connection.begin():
            # PostgreSQL itself prevents data writes in this transaction.
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))

            # 2. Database size includes other tables and PostgreSQL overhead.
            database_df = pd.read_sql(text("""
                SELECT pg_database_size(current_database()) AS database_bytes
            """), connection)

            # 3. Table totals include indexes and oversized-value (TOAST) storage.
            tables_df = pd.read_sql(text("""
                SELECT c.relname AS table_name,
                       pg_total_relation_size(c.oid) AS total_bytes
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'bronze'
                  AND c.relname IN ('prospects_2026_batches', 'prospects_2026_rows')
                  AND c.relkind = 'r'
                ORDER BY c.relname
            """), connection)
            if len(tables_df) != 2:
                raise ValueError("Expected Bronze tables missing")

            # 4. Count stored rows separately from metadata to detect discrepancies.
            snapshots_df = pd.read_sql(text("""
                SELECT b.loaded_at AS loaded_at_utc,
                       b.source_row_count AS expected_rows,
                       count(r.source_sheet_row) AS stored_rows
                FROM bronze.prospects_2026_batches b
                LEFT JOIN bronze.prospects_2026_rows r USING (snapshot_id)
                GROUP BY b.snapshot_id, b.loaded_at, b.source_row_count
                ORDER BY b.loaded_at
            """), connection)
except (SQLAlchemyError, ValueError):
    raise SystemExit("Storage check failed. Check the connection and Bronze tables; no data was changed. Do not share credentials.") from None
finally:
    if engine is not None:
        engine.dispose()

# 5. Convert bytes into MiB (1 MiB = 1,048,576 bytes) for readable output.
database_df["database_mib"] = (database_df["database_bytes"] / 1024**2).round(2)
tables_df["total_mib"] = (tables_df["total_bytes"] / 1024**2).round(2)
snapshots_df["loaded_at_utc"] = pd.to_datetime(snapshots_df["loaded_at_utc"], utc=True)
snapshots_df["count_matches"] = snapshots_df["expected_rows"].eq(snapshots_df["stored_rows"])

print("Neon storage check (read-only):")
print(database_df.to_string(index=False))
print("\nBronze tables, including indexes:")
print(tables_df.to_string(index=False))
print("\nStored snapshots:", len(snapshots_df))
print(snapshots_df.to_string(index=False))
print("Total rows across stored snapshots:", int(snapshots_df["stored_rows"].sum()))
if not snapshots_df.empty and snapshots_df["count_matches"].all():
    print("Snapshot row-count check: PASS")
else:
    print("Snapshot row-count check: REVIEW REQUIRED (missing snapshot or count mismatch)")
print("PostgreSQL sizes are not an exact Neon plan-usage measurement; also check the Neon console.")
print("No source values printed. No data changed. Do not schedule full snapshots yet.")
