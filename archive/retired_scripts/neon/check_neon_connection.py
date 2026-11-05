from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# Load .env from the repository folder
project_folder = Path(__file__).resolve().parents[2]
load_dotenv(project_folder / ".env")

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError("DATABASE_URL is missing from the repository's .env file.")

# Tell SQLAlchemy to connect using our psycopg driver
connection_url = make_url(database_url).set(
    drivername="postgresql+psycopg"
)

engine = create_engine(
    connection_url,
    connect_args={"connect_timeout": 30}
)

# Read database information without changing anything
query = text("""
    SELECT schema_name
    FROM information_schema.schemata
    WHERE schema_name IN (
        'bronze', 'silver', 'gold',
        'quality', 'audit', 'analytics_ml'
    )
    ORDER BY schema_name;
""")

with engine.connect() as connection:
    df = pd.read_sql(query, connection)

engine.dispose()

print(df.to_string(index=False))
print(f"\nSchemas found: {len(df)}")
