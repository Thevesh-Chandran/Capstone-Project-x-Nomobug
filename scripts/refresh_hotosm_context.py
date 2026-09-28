"""Refresh location context from the already loaded pinned waterways snapshot."""
from google.cloud import bigquery
from load_hotosm_waterways import PROJECT, LOCATION, EXPECTED_SHA256, CONTEXT_TABLE, context_query


def main():
    with bigquery.Client(project=PROJECT, location=LOCATION) as client:
        sql = context_query(EXPECTED_SHA256)
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True))
        if dry.total_bytes_processed > 100 * 1024 * 1024:
            raise SystemExit('Waterway context refresh exceeds 100 MiB guard')
        client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=100 * 1024 * 1024)).result(timeout=180)
        print(f'Refreshed waterway context: {client.get_table(CONTEXT_TABLE).num_rows} locations')


if __name__ == '__main__':
    main()
