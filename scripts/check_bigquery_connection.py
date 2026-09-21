"""Read-only BigQuery setup check. No query jobs, uploads, or dataset creation."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery
from google.auth.exceptions import GoogleAuthError
from google.api_core.exceptions import GoogleAPICallError, NotFound

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
project = os.getenv("NOMOBUG_BQ_PROJECT", "").strip()
location = os.getenv("NOMOBUG_BQ_LOCATION", "").strip()
if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project) or not location:
    raise SystemExit("Set NOMOBUG_BQ_PROJECT and NOMOBUG_BQ_LOCATION in .env first.")

client = None
try:
    # Uses Application Default Credentials, NOT the Sheets/Calendar OAuth token.
    client = bigquery.Client(project=project, location=location)
    print("BigQuery connection check (metadata only):")
    for layer in ["bronze", "silver", "gold", "quality", "audit", "analytics_ml"]:
        try:
            dataset = client.get_dataset(f"{project}.{layer}")
        except NotFound:
            print(layer + ": missing; no dataset created")
            continue
        print(layer + ": accessible; region " + dataset.location)
        if dataset.location.lower() != location.lower():
            raise SystemExit("Dataset region differs from configured location. Stop and review; do not recreate it.")
    print("Metadata requests completed. No queries or writes performed.")
    print("This does NOT verify billing, IAM write access, or cost-control settings.")
except (GoogleAuthError, GoogleAPICallError, ValueError):
    raise SystemExit("BigQuery setup check failed. Confirm ADC sign-in, project and API access. No data changed; do not share tokens.") from None
finally:
    if client is not None:
        client.close()
