"""Read-only current callback features using the frozen dbt transformations.

All source substitutions are session-local BigQuery temporary tables. Predictor
queries have no outcome CTE or target columns. Customer-level evidence is written
only under ignored outputs; permanent sources and model bundles are unchanged.
An exact normalized Calendar address hash may reuse a pinned geocode with one
nonconflicting coordinate/tier; this denotes a mapped area, not verified property.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

import pandas as pd

try:
    from scripts import benchmark_warranty_models as b
    from scripts import freeze_callback_prospective as prospective
    from scripts import refresh_callback_validation as replay
    from scripts.load_calendar_bronze import FIELDS
    from scripts.operational_source_contracts import PREFIXES
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    import freeze_callback_prospective as prospective
    import refresh_callback_validation as replay
    from load_calendar_bronze import FIELDS
    from operational_source_contracts import PREFIXES

LOCAL = ZoneInfo('Asia/Kuala_Lumpur')
COMPILED = b.ROOT / 'dbt/target/compiled/nomobug/models'
BASELINE = b.ROOT / 'outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json'
PIN = b.ROOT / 'config/cp2_live_feature_contract.json'
KEYS = ['population', 'sales_record_id', 'anchor_date']
REQUIRED_TABS = ('SALES', 'PAYMENT LINK', 'WARRANTY CLAIM')
OUTCOME_COLUMNS = {'warranty_signal_within_30d', 'warranty_claim_count_30d'}
SOURCE_CHUNK_BYTES = 3 * 1024**2


def aware(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Source and run timestamps require timezone')
    return result.astimezone(timezone.utc)


def validate_frozen_source_contract():
    """Stop if source macros or compiled feature SQL drift from frozen v5."""
    registry = json.loads((b.ROOT / 'config/cp2_model_current.json').read_text(encoding='utf-8'))
    model = b.ROOT / registry['bundle_relative_path'] / 'bundle.json'
    model_digest = hashlib.sha256(model.read_bytes()).hexdigest()
    if model_digest != registry['bundle_sha256']:
        raise ValueError('Current frozen model bundle differs from registry')
    manifest = json.loads(model.read_text(encoding='utf-8'))
    declared = manifest['upstream_contract_hashes']
    for name in ('calendar_history_available', 'calendar_snapshot_observation_sql',
                 'warranty_anchor_dataset_sql'):
        path = f'dbt/macros/{name}.sql'
        # v5 retained an older Windows-key entry for the anchor macro. The
        # canonical slash entry is the newer corrected contract and wins.
        expected = declared.get(path, declared.get(path.replace('/', '\\')))
        actual = hashlib.sha256((b.ROOT / path).read_bytes()).hexdigest()
        if expected is None or actual != expected:
            raise ValueError('Frozen dbt macro contract differs')
    pin = json.loads(PIN.read_text(encoding='utf-8'))
    if pin['bundle_sha256'] != model_digest or pin['version'] != 'cp2_live_features_v1':
        raise ValueError('Live feature pin belongs to another model bundle')
    required = {'sales.sql', 'gold/sales_package_facts.sql', 'calendar_events.sql',
        'calendar_event_matches.sql', 'calendar_event_locations.sql',
        'gold/calendar_service_event_facts.sql',
        'analytics_ml/warranty_anchor_environment_features.sql',
        'analytics_ml/warranty_callback_fixed_horizon_dataset.sql'}
    if set(pin['compiled_query_hashes']) != required:
        raise ValueError('Live feature compiled SQL pin inventory differs')
    for path, expected in pin['compiled_query_hashes'].items():
        # The existing successful-run receipt hashes the same decoded SQL text
        # that BigQuery executes; pathlib normalizes Windows CRLF on read_text.
        actual = hashlib.sha256((COMPILED / path).read_text(encoding='utf-8').encode()).hexdigest()
        if actual != expected:
            raise ValueError('Compiled live feature SQL differs from frozen contract')
    return hashlib.sha256(PIN.read_bytes()).hexdigest()


def validate_calendar(snapshot, now):
    metadata = snapshot['metadata']
    extracted = aware(metadata['extracted_at'])
    if (metadata.get('format_version') != 1 or metadata.get('source_type') != 'Google Calendar'
            or metadata.get('timezone') != 'Asia/Kuala_Lumpur' or metadata.get('show_deleted') is not True
            or metadata.get('calendar_count') != 6 or extracted > now
            or (now - extracted).total_seconds() > 3600):
        raise ValueError('Calendar source freshness or coverage contract failed')
    start, end = date.fromisoformat(metadata['window_start']), date.fromisoformat(metadata['window_end'])
    if start > date(2023, 1, 1) or end < now.astimezone(LOCAL).date():
        raise ValueError('Calendar historical/current window is incomplete')
    if metadata.get('event_row_count') != len(snapshot['records']):
        raise ValueError('Calendar source row count differs')
    return min(end, extracted.astimezone(LOCAL).date() - timedelta(days=1), now.astimezone(LOCAL).date() - timedelta(days=1))


def calendar_delta(old, new):
    """Keep reviewed old IDs; use stable negative IDs for newly observed events."""
    delta, replaced, invalid_geo, summary = replay.source_delta(old, new)
    identity = lambda row: (row['calendar_id'], row['event_id'])
    known = {identity(row): row for row in old['records']}
    invalid_review = []
    for row in delta:
        key = identity(row)
        if key not in known:
            encoded = json.dumps(key, separators=(',', ':')).encode()
            row['calendar_event_row'] = -int(hashlib.sha256(encoded).hexdigest()[:15], 16) - 1
        elif any(row.get(field) != known[key].get(field) for field in
                 ('summary', 'description', 'location', 'status', 'start_raw', 'end_raw')):
            invalid_review.append(row['calendar_event_row'])
    IDs = [row['calendar_event_row'] for row in delta]
    retained = [row['calendar_event_row'] for row in old['records'] if row['calendar_event_row'] not in replaced]
    if len(set(IDs + retained)) != len(IDs + retained):
        raise ValueError('Stable Calendar row identity collision')
    return delta, replaced, invalid_geo, invalid_review, summary


def _projection(fields, int_fields=(), bool_fields=()):
    pieces = []
    for field in fields:
        if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', field):
            raise ValueError('Invalid source column')
        expression = f"JSON_VALUE(item,'$.{field}')"
        if field in int_fields:
            expression = f'CAST({expression} AS INT64)'
        if field in bool_fields:
            expression = f'CAST({expression} AS BOOL)'
        pieces.append(f'{expression} AS {field}')
    return ','.join(pieces)


def source_chunks(records, maximum_bytes=SOURCE_CHUNK_BYTES):
    """Keep each nested BQ JSON string comfortably under the HTTP limit."""
    result, chunk, size = [], [], 2
    for record in records:
        encoded = json.dumps(record, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        width = len(encoded.encode('utf-8')) + 1
        if width + 2 > maximum_bytes:
            raise ValueError('Single source row exceeds bounded request size')
        if chunk and size + width > maximum_bytes:
            result.append(chunk)
            chunk, size = [], 2
        chunk.append(record)
        size += width
    if chunk or not records: result.append(chunk)
    return result


def _address_tools():
    """Load the existing audited address extractor without its network paths."""
    scripts_dir = str(b.ROOT / 'scripts')
    added = scripts_dir not in sys.path
    if added: sys.path.insert(0, scripts_dir)
    try:
        try:
            from scripts import pilot_geoapify_calendar as pilot
        except ModuleNotFoundError:
            import pilot_geoapify_calendar as pilot
        return pilot
    finally:
        if added: sys.path.remove(scripts_dir)


def exact_address_hash_candidates(rows):
    """Emit only eligible hashes from the production geocoder's exact pipeline."""
    pilot = _address_tools()
    result = []
    seen = set()
    for row in rows:
        event_row = int(row['calendar_event_row'])
        if event_row >= 0 or event_row in seen:
            raise ValueError('Unexpected new Calendar address candidate grain')
        seen.add(event_row)
        block, _ = pilot.address_block(row.get('description'), row.get('extracted_line'))
        address = pilot.sanitized_address_candidate(block)
        if address and pilot.ADDRESS_PLACEHOLDER.fullmatch(address.strip()): address = None
        address = (address or pilot.sanitized_address_candidate(row.get('location'))
                   or pilot.sanitized_address_candidate(row.get('description_text')))
        if not pilot.eligible_address(address): continue
        normalized = pilot.normalized_candidate_key(address)
        if not normalized: continue
        result.append({'calendar_event_row': event_row,
            'address_hash': hashlib.sha256(normalized.encode()).hexdigest()})
    return result


def address_candidate_sql():
    """Copy the original BigQuery extracted-line expression, not a shortcut."""
    expression = _address_tools().calendar_address_expr('e.description_text')
    return rf"""WITH events AS (
    SELECT c.calendar_event_row, b.description, b.location,
        REGEXP_REPLACE(REGEXP_REPLACE(COALESCE(b.description, ''),
            r'(?i)</?(?:p|div|li|br)\b[^>]*>', '\n'), r'<[^>]+>', '')
            AS description_text
    FROM live_calendar_events c
    JOIN live_calendar_raw b USING (calendar_event_row)
    WHERE c.service_candidate AND c.calendar_event_row < 0
), extracted AS (
    SELECT e.*, {expression} AS extracted_line FROM events e
)
SELECT calendar_event_row, description, location, description_text, extracted_line
FROM extracted"""


def geocode_reuse_sql(source):
    """Reuse only one exact hash's nonconflicting coordinate and precision tier."""
    return f"""CREATE TEMP TABLE live_geocodes AS
WITH candidates AS (
    SELECT CAST(JSON_VALUE(item,'$.calendar_event_row') AS INT64) AS new_event_row,
        JSON_VALUE(item,'$.address_hash') AS address_hash
    FROM UNNEST(JSON_QUERY_ARRAY(@address_candidates)) AS item
), matched AS (
    SELECT c.new_event_row, g.*
    FROM candidates c JOIN {source} g USING (address_hash)
    WHERE g.calendar_event_row NOT IN UNNEST(@invalid_geocodes)
      AND g.latitude BETWEEN 0.5 AND 7.6 AND g.longitude BETWEEN 99 AND 120
      AND g.precision_tier IS NOT NULL
), unique_location AS (
    SELECT new_event_row
    FROM matched GROUP BY new_event_row
    HAVING COUNT(DISTINCT TO_JSON_STRING(STRUCT(latitude, longitude, precision_tier))) = 1
), chosen AS (
    SELECT m.* FROM matched m JOIN unique_location USING (new_event_row)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY new_event_row ORDER BY calendar_event_row) = 1
)
SELECT * FROM {source}
UNION ALL
SELECT c.* EXCEPT(new_event_row) REPLACE (
    c.new_event_row AS calendar_event_row,
    'pinned_quality_exact_hash_reuse' AS geocode_provider,
    'exact_address_hash_reuse_not_verified_property' AS coordinate_source,
    FALSE AS manual_override_protected)
FROM chosen c"""


def validate_weather_records(records, watermark):
    keys = set()
    required = {'weather_location_id', 'weather_date', 'precipitation_sum_mm',
        'temperature_2m_mean_c', 'relative_humidity_2m_mean_pct', 'soil_moisture_0_to_7cm_mean'}
    for row in records:
        if not required.issubset(row) or not re.fullmatch(r'[a-fA-F0-9]{64}', row['weather_location_id']):
            raise ValueError('Weather source schema or grid identity differs')
        day = date.fromisoformat(row['weather_date'])
        key = (row['weather_location_id'], day)
        if key in keys or day > watermark:
            raise ValueError('Duplicate or future/partial-day weather observation')
        keys.add(key)


def adapt_anchor_sql(source, watermark, *, predictors):
    """Change only observation/eligibility/output, retaining contracted features."""
    source, count = re.subn(r'with observation as \(.*?\), uncertain_packages as \(',
        f"with observation as (SELECT DATE '{watermark.isoformat()}' AS observed_through), uncertain_packages as (",
        source, flags=re.S)
    if count != 1:
        raise ValueError('Unexpected compiled observation SQL')
    if 'h.event_created_ts <= a.event_end_ts' not in source or 'history_links as (' not in source:
        raise ValueError('Compiled SQL lacks corrected history availability contract')
    mature_clause = 'and date_add(event_date_local, interval 30 day) <= o.observed_through'
    if source.count(mature_clause) != 1:
        raise ValueError('Unexpected compiled anchor maturity SQL')
    if predictors:
        # Enforce availability before ROW_NUMBER/COUNT package-session
        # disambiguation; a later-created appointment cannot veto an anchor.
        match = 'and f.event_date_local >= p.closed_date'
        if source.count(match) != 1: raise ValueError('Unexpected compiled candidate timing SQL')
        source = source.replace(match, match + '\n      and f.event_created_ts <= @as_of'
            '\n      and f.event_end_ts <= @as_of')
        source = source.replace(mature_clause,
            'and event_date_local >= DATE_SUB(DATE(@as_of, "Asia/Kuala_Lumpur"), INTERVAL 30 DAY)'
            '\n      and event_end_ts <= @as_of and event_created_ts <= @as_of')
        source, count = re.subn(r'\), outcomes as \(.*?\n\)\nselect a\.population',
            ')\nselect a.population', source, flags=re.S)
        if count != 1:
            raise ValueError('Unexpected compiled outcome CTE')
        source = source.replace('    w.warranty_signal_within_30d, w.warranty_claim_count_30d,\n', '')
        source = source.replace('join outcomes w using (calendar_event_row)\n', '')
        source = source.replace('    a.event_date_local as anchor_date,',
            '    a.event_start_ts as service_start_at, a.event_end_ts as service_end_at,\n'
            '    @snapshot_at as feature_snapshot_at, @as_of as prediction_at,\n'
            '    a.event_date_local as anchor_date,')
        for token in OUTCOME_COLUMNS | {'outcomes as ('}:
            if token in source:
                raise ValueError('Outcome leaked into live predictor query')
    return source


def build_stages(old, calendar_snapshot, sheet_snapshots, *, now, weather_records=None):
    """Return parameterized session stages without contacting the warehouse."""
    watermark = validate_calendar(calendar_snapshot, now)
    delta, replaced, invalid_geo, invalid_review, summary = calendar_delta(old, calendar_snapshot)
    params = {'delta': delta, 'replaced': replaced, 'invalid_geocodes': invalid_geo,
              'invalid_reviews': invalid_review, 'as_of': now,
              'snapshot_at': aware(calendar_snapshot['metadata']['extracted_at'])}
    replacement = {}
    stages, hashes = [], {}
    source_lineage_literals = {}
    raw = (f'CREATE TEMP TABLE live_calendar_raw AS SELECT {",".join(FIELDS)} '
           f'FROM `{b.PROJECT}.bronze.{replay.OLD_TABLE}` '
           'WHERE calendar_event_row NOT IN UNNEST(@replaced) '
           'AND SAFE_CAST(start_raw AS TIMESTAMP) <= @as_of '
           'AND (SAFE_CAST(created_raw AS TIMESTAMP) IS NULL '
           'OR SAFE_CAST(created_raw AS TIMESTAMP) <= @as_of) UNION ALL SELECT '
           + _projection(FIELDS, ('calendar_event_row',), ('is_all_day',))
           + ' FROM UNNEST(JSON_QUERY_ARRAY(@delta)) AS item '
           "WHERE SAFE_CAST(JSON_VALUE(item,'$.start_raw') AS TIMESTAMP) <= @as_of "
           "AND (SAFE_CAST(JSON_VALUE(item,'$.created_raw') AS TIMESTAMP) IS NULL "
           "OR SAFE_CAST(JSON_VALUE(item,'$.created_raw') AS TIMESTAMP) <= @as_of)")
    # Future scheduled appointments are excluded even from matching, so neither
    # matched-sale selection nor duplicate-session counts can see future dates.
    stages.append(('calendar_raw', raw))
    replacement[f'`{b.PROJECT}`.`bronze`.`{replay.OLD_TABLE}`'] = 'live_calendar_raw'
    for tab in REQUIRED_TABS:
        snapshot = sheet_snapshots[tab]
        metadata = snapshot['metadata']
        extracted = aware(metadata['extracted_at'])
        if extracted > now or (now - extracted).total_seconds() > 3600:
            raise ValueError('Sheets source freshness contract failed')
        params['snapshot_at'] = max(params['snapshot_at'], extracted)
        if metadata.get('source_tab') != tab or metadata.get('source_row_count') != len(snapshot['records']):
            raise ValueError('Sheets source metadata differs')
        columns = [f'source_column_{i:03d}' for i in range(1, metadata['source_column_count'] + 1)]
        fields = ['source_sheet_row'] + columns
        if any(set(row) != set(fields) for row in snapshot['records']):
            raise ValueError('Sheets positional source schema differs')
        prefix = PREFIXES[tab]
        for index, chunk in enumerate(source_chunks(snapshot['records'])):
            parameter = f'{prefix}_{index:03d}'
            params[parameter] = chunk
            verb = (f'CREATE TEMP TABLE live_{prefix}_raw AS SELECT ' if index == 0
                    else f'INSERT INTO live_{prefix}_raw SELECT ')
            stages.append((parameter + '_raw', verb
                + _projection(fields, ('source_sheet_row',))
                + f' FROM UNNEST(JSON_QUERY_ARRAY(@{parameter})) AS item'))
        # The compiled sources are pinned; substitutions are strictly these
        # approved source prefixes and do not rewrite production configuration.
        compiled_sources = '\n'.join((COMPILED / path).read_text(encoding='utf-8') for path in
            ['sales.sql', 'calendar_event_matches.sql'])
        relations = set(re.findall(r'`[^`]+`\.`bronze`\.`' + prefix + r'_[a-f0-9]+`', compiled_sources))
        if len(relations) != 1:
            raise ValueError('Unexpected compiled operational source pin')
        for relation in relations:
            replacement[relation] = f'live_{prefix}_raw'
            source_lineage_literals[tab] = (relation.rsplit('`', 2)[-2], snapshot['table_name'])
    # Existing weather rows remain available. Supplemental refreshed rows replace
    # overlapping grid/date keys; no duplicates can inflate completeness counts.
    if weather_records is not None:
        validate_weather_records(weather_records, watermark)
        params['weather'] = weather_records
        weather_fields = ['weather_location_id', 'weather_date', 'precipitation_sum_mm',
            'temperature_2m_mean_c', 'relative_humidity_2m_mean_pct', 'soil_moisture_0_to_7cm_mean']
        weather_select = []
        for field in weather_fields:
            value = f"JSON_VALUE(item,'$.{field}')"
            if field == 'weather_date': value = f'CAST({value} AS DATE)'
            elif field != 'weather_location_id': value = f'CAST({value} AS FLOAT64)'
            weather_select.append(f'{value} AS {field}')
        stages.append(('weather_refresh', 'CREATE TEMP TABLE live_weather_refresh AS SELECT '
            + ','.join(weather_select) + ' FROM UNNEST(JSON_QUERY_ARRAY(@weather)) item'))
        weather_source = (COMPILED / 'analytics_ml/warranty_anchor_environment_features.sql').read_text(encoding='utf-8')
        weather_tables = set(re.findall(r'`[^`]+`\.`quality`\.`open_meteo[^`]+`', weather_source))
        if len(weather_tables) != 1: raise ValueError('Unexpected frozen weather source')
        weather_table = next(iter(weather_tables))
        stages.append(('weather', 'CREATE TEMP TABLE live_weather AS SELECT '
            + ','.join(weather_fields) + f' FROM {weather_table} old WHERE NOT EXISTS '
            '(SELECT 1 FROM live_weather_refresh fresh WHERE fresh.weather_location_id=old.weather_location_id '
            'AND fresh.weather_date=old.weather_date) UNION ALL SELECT * FROM live_weather_refresh'))
        replacement[weather_table] = 'live_weather'
    models = [('sales', 'sales.sql', 'silver'),
        ('sales_package_facts', 'gold/sales_package_facts.sql', 'gold'),
        ('calendar_events', 'calendar_events.sql', 'silver'),
        ('calendar_event_matches', 'calendar_event_matches.sql', 'silver'),
        ('calendar_event_locations', 'calendar_event_locations.sql', 'silver'),
        ('calendar_service_event_facts', 'gold/calendar_service_event_facts.sql', 'gold'),
        ('warranty_anchor_environment_features', 'analytics_ml/warranty_anchor_environment_features.sql', 'analytics_ml')]
    for name, path, schema in models:
        source = (COMPILED / path).read_text(encoding='utf-8')
        hashes[path] = hashlib.sha256(source.encode()).hexdigest()
        if name == 'calendar_event_locations':
            sources = set(re.findall(r'`[^`]+`\.`quality`\.`calendar_event_geocodes[^`]+`', source))
            if len(sources) != 1: raise ValueError('Unexpected pinned Calendar geocode source')
            original_geocodes = next(iter(sources))
            stages.append(('geocode_reuse', geocode_reuse_sql(original_geocodes)))
            stages.append(('geocode_reuse_summary',
                "SELECT COUNTIF(coordinate_source='exact_address_hash_reuse_not_verified_property') "
                'AS reused_event_rows FROM live_geocodes'))
            replacement[original_geocodes] = 'live_geocodes'
        if name == 'sales':
            old_literal, fresh_literal = source_lineage_literals['SALES']
            if not re.fullmatch(r'sales_[a-f0-9]{64}', fresh_literal) or source.count(f"'{old_literal}'") != 2:
                raise ValueError('Unexpected compiled SALES lineage literals')
            source = source.replace(f"'{old_literal}'", f"'{fresh_literal}'")
        for old_name, new_name in replacement.items(): source = source.replace(old_name, new_name)
        if name == 'calendar_events':
            source = source.replace('and r.event_id = c.event_id',
                'and r.event_id = c.event_id and c.calendar_event_row NOT IN UNNEST(@invalid_reviews)')
        if name == 'calendar_event_locations':
            source += '\n AND e.calendar_event_row NOT IN UNNEST(@invalid_geocodes)'
        temporary = 'live_' + name
        stages.append((name, f'CREATE TEMP TABLE {temporary} AS\n{source.rstrip().rstrip(";")}'))
        replacement[f'`{b.PROJECT}`.`{schema}`.`{name}`'] = temporary
        if name == 'calendar_events':
            stages.append(('address_candidates', address_candidate_sql()))
    source = (COMPILED / 'analytics_ml/warranty_callback_fixed_horizon_dataset.sql').read_text(encoding='utf-8')
    hashes['analytics_ml/warranty_callback_fixed_horizon_dataset.sql'] = hashlib.sha256(source.encode()).hexdigest()
    for old_name, new_name in replacement.items(): source = source.replace(old_name, new_name)
    stages.extend([('predictors', adapt_anchor_sql(source, watermark, predictors=True)),
                   ('mature_labels', adapt_anchor_sql(source, watermark, predictors=False))])
    return stages, params, {'calendar_delta': summary, 'complete_outcomes_through': watermark.isoformat(),
        'compiled_query_hashes': hashes, 'calendar_snapshot_id': calendar_snapshot['metadata']['snapshot_id'],
        'sheet_snapshot_ids': {tab: sheet_snapshots[tab]['metadata']['snapshot_id'] for tab in REQUIRED_TABS},
        'source_extracted_at': calendar_snapshot['metadata']['extracted_at'],
        'calendar_coverage_start': calendar_snapshot['metadata']['window_start'],
        'calendar_coverage_end_requested': calendar_snapshot['metadata']['window_end'],
        'complete_calendar_inventory': True,
        'fresh_weather_rows': len(weather_records or [])}


def derive(calendar_snapshot, sheet_snapshots, run_dir, *, weather_records=None, now=None, client=None):
    """Persist predictor/mature-label inputs and return a PII-free run receipt."""
    from google.cloud import bigquery
    now = aware(now or datetime.now(timezone.utc))
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_relative_to((b.ROOT / 'outputs').resolve()):
        raise ValueError('Private features must stay under ignored outputs')
    contract_sha256 = validate_frozen_source_contract()
    if (run_dir / 'features_receipt.json').exists():
        raise ValueError('Feature run evidence already exists')
    old = json.loads(BASELINE.read_text(encoding='utf-8'))
    if old['metadata']['snapshot_id'] != replay.OLD_TABLE.split('_')[-1]:
        raise ValueError('Unexpected stable Calendar baseline snapshot')
    stages, values, receipt = build_stages(old, calendar_snapshot, sheet_snapshots, now=now, weather_records=weather_records)
    for name, value in values.items():
        if name not in {'as_of', 'snapshot_at'} and len(json.dumps(value, ensure_ascii=False,
                separators=(',', ':'), allow_nan=False).encode()) > SOURCE_CHUNK_BYTES:
            raise ValueError('Temporary source query parameter exceeds bounded request size')
    parameters = [bigquery.ScalarQueryParameter(name, 'TIMESTAMP', value) if name in {'as_of', 'snapshot_at'}
        else bigquery.ArrayQueryParameter(name, 'INT64', value) if name in {'replaced', 'invalid_geocodes', 'invalid_reviews'}
        else bigquery.ScalarQueryParameter(name, 'STRING', json.dumps(value, ensure_ascii=False,
            separators=(',', ':'), allow_nan=False))
        for name, value in values.items()]
    own_client = client is None
    client = client or bigquery.Client(project=b.PROJECT, location=b.LOCATION)
    session_id, jobs, frames = None, [], {}
    candidate_count = reused_events = 0
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        for title, sql in stages:
            # Include only used parameters: prevents passing unrelated large PII
            # payloads with every stage and keeps Google request bodies bounded.
            used = {parameter.name for parameter in parameters if re.search(r'@' + re.escape(parameter.name) + r'\b', sql)}
            config = bigquery.QueryJobConfig(maximum_bytes_billed=b.MAX_BYTES,
                query_parameters=[parameter for parameter in parameters if parameter.name in used],
                create_session=session_id is None)
            if session_id:
                config.connection_properties = [bigquery.ConnectionProperty('session_id', session_id)]
            job = client.query(sql, job_config=config)
            try: rows = job.result(timeout=300)
            except Exception:
                job.cancel()
                try: job.result(timeout=30)
                except Exception: pass
                raise
            if session_id is None: session_id = job.session_info.session_id
            jobs.append({'stage': title, 'job_id': job.job_id, 'bytes_processed': job.total_bytes_processed,
                'bytes_billed': job.total_bytes_billed})
            if title == 'address_candidates':
                candidate_rows = [dict(row) for row in rows]
                candidates = exact_address_hash_candidates(candidate_rows)
                candidate_count = len(candidates)
                serialized = json.dumps(candidates, separators=(',', ':'), allow_nan=False)
                if len(serialized.encode()) > SOURCE_CHUNK_BYTES:
                    raise ValueError('Exact-address hash candidate parameter exceeds request cap')
                parameters.append(bigquery.ScalarQueryParameter('address_candidates', 'STRING', serialized))
            if title == 'geocode_reuse_summary':
                reused_events = int(next(iter(rows))['reused_event_rows'])
            if title in {'predictors', 'mature_labels'}:
                frames[title] = pd.DataFrame([dict(row) for row in rows], columns=[field.name for field in rows.schema])
        for title, frame in frames.items():
            if frame.duplicated(KEYS).any(): raise ValueError('Duplicate live callback anchors')
            if title == 'predictors' and OUTCOME_COLUMNS & set(frame):
                raise ValueError('Outcome present in predictor input')
        if not frames['predictors'].empty:
            prospective.configure_contracts(False)
            prospective.prepare_scoring_frame(frames['predictors'], 'candidate_v5')
        receipt['predictor_input_sha256'] = b.persist_dataset_input(frames['predictors'], run_dir / 'predictors')
        receipt['mature_input_sha256'] = b.persist_dataset_input(frames['mature_labels'], run_dir / 'mature_labels')
        receipt.update(predictor_rows=len(frames['predictors']), mature_rows=len(frames['mature_labels']),
            frozen_feature_contract_sha256=contract_sha256,
            eligible_new_address_hash_candidates=candidate_count,
            exact_hash_reused_calendar_event_rows=reused_events,
            predictor_new_calendar_rows_with_reused_location=int(((frames['predictors']['anchor_event_row'] < 0)
                & frames['predictors']['location_uncertainty_radius_m'].notna()).sum()),
            predictor_rows_missing_location=int(frames['predictors']['location_uncertainty_radius_m'].isna().sum()),
            predictor_rows_complete_prior_30d_weather=int(frames['predictors']['complete_prior_30d_weather'].fillna(False).sum()),
            predictor_input_relative_path=str((run_dir / 'predictors/dataset_input.json').relative_to(b.ROOT)),
            mature_input_relative_path=str((run_dir / 'mature_labels/dataset_input.json').relative_to(b.ROOT)),
            query_jobs=jobs, bytes_processed=sum(job['bytes_processed'] or 0 for job in jobs),
            temporary_tables_only=True, query_maximum_bytes_billed=b.MAX_BYTES,
            derived_at_utc=datetime.now(timezone.utc).isoformat(),
            limitations=['Calendar service end is recorded scheduling, not proof of completion.',
                'Previously unmapped or changed Calendar addresses retain missing location features.',
                'Exact normalized address-hash reuse identifies a mapped area proxy, not a verified same property.',
                'Source field revisions cannot reconstruct unsaved historical field versions.'])
        (run_dir / 'features_receipt.json').write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding='utf-8')
        return receipt
    finally:
        if session_id:
            config = bigquery.QueryJobConfig(maximum_bytes_billed=b.MAX_BYTES,
                connection_properties=[bigquery.ConnectionProperty('session_id', session_id)])
            try: client.query('CALL BQ.ABORT_SESSION();', job_config=config).result(timeout=30)
            except Exception:
                # Session cleanup must not replace the actionable stage error.
                pass
        if own_client: client.close()
