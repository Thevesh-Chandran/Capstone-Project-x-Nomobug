"""Read-only, aggregate-only checkpoint after the dbt build. No customer values printed."""
from google.cloud import bigquery

# Existing Google Application Default Credentials are used; never paste a key here.
client = bigquery.Client(project="profound-keel-500007-s4", location="asia-southeast1")
query = """
SELECT row_class, COUNT(*) AS row_count,
  COUNTIF(first_reply_needs_review) AS date_review,
  COUNTIF(customer_type_needs_review) AS customer_type_review,
  COUNTIF(pest_needs_review) AS pest_review,
  COUNTIF(status_needs_review) AS status_review,
  COUNTIF(pic_needs_review) AS pic_review,
  COUNTIF(acquisition_needs_review) AS acquisition_review,
  COUNTIF(acquisition_group = 'UNKNOWN') AS unknown_source,
  COUNTIF(acquisition_group = 'MISSING') AS missing_source
FROM `profound-keel-500007-s4.silver.prospects_2026`
GROUP BY row_class
ORDER BY row_class
"""
# Ceiling applies per query, not to total cloud spending.
settings = bigquery.QueryJobConfig(maximum_bytes_billed=104857600)
try:
    result = client.query(query, job_config=settings).result()
    import pandas as pd
    df = pd.DataFrame([dict(row) for row in result])
    print(df.to_string(index=False))
    print("Unknown and review flags are retained records, not deleted rows or failed sales.")
finally:
    client.close()
