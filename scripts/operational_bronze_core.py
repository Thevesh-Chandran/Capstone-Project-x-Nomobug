"""Small loader helpers, isolated so tests do not contact Google."""
import hashlib
import json
from google.cloud import bigquery
from google.api_core.exceptions import NotFound


def prepare_snapshot(tab, df, header_map, lineage, expected_headers, prefix):
    columns = list(header_map)
    if [' '.join(h.split()) for h in header_map.values()] != expected_headers:
        raise ValueError(f'{tab}: header layout changed; review before loading')
    if columns != [f'source_column_{n:03d}' for n in range(1, len(columns) + 1)]:
        raise ValueError('Unexpected positional columns')
    if list(df.columns) != ['source_sheet_row'] + columns or df.empty:
        raise ValueError('Empty or unexpected source frame')
    if df['source_sheet_row'].tolist() != list(range(lineage['header_row'] + 1, lineage['header_row'] + 1 + len(df))):
        raise ValueError('Source row positions changed')
    records = df.to_dict('records')
    payload = {'version': 1, 'tab': tab, 'source': lineage['spreadsheet_id'],
        'header_row': lineage['header_row'], 'headers': header_map, 'records': records}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    if len(encoded) > 100 * 1024**2:
        raise ValueError('Snapshot exceeds 100 MiB payload gate')
    digest = hashlib.sha256(encoded).hexdigest()
    schema = [bigquery.SchemaField('source_sheet_row', 'INTEGER', mode='REQUIRED')]
    schema += [bigquery.SchemaField(c, 'STRING', mode='REQUIRED', description=header_map[c]) for c in columns]
    metadata = {'format_version': 1, 'snapshot_id': digest, 'source_tab': tab,
        'workbook': lineage['workbook'], 'header_row': lineage['header_row'],
        'source_column_count': len(columns), 'source_row_count': len(df),
        'extracted_at': lineage['extracted_at'], 'extraction_started_at': lineage['started_at']}
    return {'table_name': prefix + '_' + digest, 'prefix': prefix, 'schema': schema,
        'records': records, 'metadata': metadata}


def load_and_verify(client, project, location, snapshot):
    table_id = f"{project}.bronze.{snapshot['table_name']}"
    try:
        table = client.get_table(table_id)
        status = 'REUSED'
    except NotFound:
        config = bigquery.LoadJobConfig(schema=snapshot['schema'], write_disposition='WRITE_EMPTY',
            destination_table_description=json.dumps(snapshot['metadata']))
        client.load_table_from_json(snapshot['records'], table_id, job_config=config,
            location=location).result(timeout=180)
        table = client.get_table(table_id)
        status = 'LOADED'
    actual_schema = [(f.name, f.field_type, f.mode, f.description or '') for f in table.schema]
    expected_schema = [(f.name, f.field_type, f.mode, f.description or '') for f in snapshot['schema']]
    if actual_schema != expected_schema:
        raise ValueError('Stored schema/header mismatch')
    stored_metadata = json.loads(table.description or '{}')
    for key in ['snapshot_id', 'source_tab', 'header_row', 'source_row_count', 'source_column_count']:
        if stored_metadata.get(key) != snapshot['metadata'][key]:
            raise ValueError('Stored metadata mismatch')
    actual = sorted((dict(row) for row in client.list_rows(table)), key=lambda row: row['source_sheet_row'])
    if actual != snapshot['records']:
        raise ValueError('Stored rows/values mismatch')
    return {'table': table_id, 'status': status, 'rows': len(actual),
        'snapshot_id': stored_metadata['snapshot_id'], 'extracted_at': stored_metadata['extracted_at']}
