"""Live extraction contract checks with no API or warehouse contact."""
from datetime import datetime, timezone
import json
import shutil

import pytest

from scripts import callback_live_features as live


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
PRIVATE_BUNDLE_UNAVAILABLE = not (
    live.b.ROOT / 'outputs/cp2-v2/prospective_callback_v2/bundle.json'
).is_file()
requires_private_bundle = pytest.mark.skipif(
    PRIVATE_BUNDLE_UNAVAILABLE,
    reason='Frozen private bundle is unavailable in this checkout; replay is verified locally',
)


def snapshot(records):
    return {'records': records, 'metadata': {'format_version': 1, 'source_type': 'Google Calendar',
        'timezone': 'Asia/Kuala_Lumpur', 'show_deleted': True, 'calendar_count': 6,
        'extracted_at': NOW.isoformat(), 'window_start': '2000-01-01', 'window_end': '2026-09-27',
        'event_row_count': len(records), 'snapshot_id': 'test'}}


def event(number, identity, **changes):
    return {'calendar_event_row': number, 'calendar_id': 'calendar', 'event_id': identity,
        'summary': 'GPC 1/3', 'description': 'unchanged', 'location': '', 'status': 'confirmed',
        'start_raw': '2026-09-27T10:00:00+08:00', 'end_raw': '2026-09-27T12:00:00+08:00', **changes}


def test_new_calendar_row_ids_are_stable_across_inventory_changes():
    old = snapshot([event(1, 'old')])
    first = snapshot([event(1, 'old'), event(2, 'new-b')])
    next_run = snapshot([event(1, 'old'), event(2, 'new-a'), event(3, 'new-b')])
    row_a = next(row for row in live.calendar_delta(old, first)[0] if row['event_id'] == 'new-b')
    row_b = next(row for row in live.calendar_delta(old, next_run)[0] if row['event_id'] == 'new-b')
    assert row_a['calendar_event_row'] == row_b['calendar_event_row'] < 0


def test_modified_review_and_geocode_are_not_inherited():
    old = snapshot([event(1, 'old')])
    new = snapshot([event(1, 'old', description='changed')])
    _, _, invalid_geo, invalid_review, _ = live.calendar_delta(old, new)
    assert invalid_geo == invalid_review == [1]


def test_metadata_only_update_preserves_review_and_location():
    old = snapshot([event(1, 'old', updated_raw='2026-09-26T00:00:00Z')])
    new = snapshot([event(1, 'old', updated_raw='2026-09-27T00:00:00Z')])
    _, _, invalid_geo, invalid_review, _ = live.calendar_delta(old, new)
    assert invalid_geo == invalid_review == []


@pytest.mark.parametrize('field,value', [('show_deleted', False), ('calendar_count', 5),
    ('extracted_at', '2026-09-26T12:00:00Z'), ('extracted_at', '2026-09-28T12:00:00Z'),
    ('window_end', '2026-09-26'), ('window_start', '2026-01-01')])
def test_calendar_incomplete_stale_future_sources_fail(field, value):
    source = snapshot([])
    source['metadata'][field] = value
    with pytest.raises(ValueError): live.validate_calendar(source, NOW)


def test_watermark_never_uses_partial_extraction_day():
    assert str(live.validate_calendar(snapshot([]), NOW)) == '2026-09-26'


def sql_fixture():
    return '''with observation as (SELECT old_date), uncertain_packages as (select 1),
candidates as (select f.* where true and f.event_date_local >= p.closed_date), anchors as (
    select c.*, date_add(event_date_local, interval 30 day) as outcome_end_date, o.observed_through
    from candidates c cross join observation o
    where anchor_order = 1 and anchor_count = 1
      and date_add(event_date_local, interval 30 day) <= o.observed_through
), history_links as (select h.event_created_ts <= a.event_end_ts), histories as (select 1), outcomes as (
    select countif(w.warranty_claim_candidate) > 0 as warranty_signal_within_30d
)
select a.population,
    a.event_date_local as anchor_date,
    w.warranty_signal_within_30d, w.warranty_claim_count_30d,
    weather.* except(calendar_event_row)
from anchors a
join histories h using (calendar_event_row)
join outcomes w using (calendar_event_row)
'''


def test_live_query_removes_entire_outcome_query_and_retains_history_gate():
    result = live.adapt_anchor_sql(sql_fixture(), NOW.date(), predictors=True)
    assert not any(token in result for token in live.OUTCOME_COLUMNS)
    assert 'outcomes as (' not in result and 'join outcomes' not in result
    assert 'h.event_created_ts <= a.event_end_ts' in result
    assert 'service_end_at' in result and 'feature_snapshot_at' in result
    assert 'event_end_ts <= @as_of' in result
    assert 'and f.event_created_ts <= @as_of' in result
    assert 'and date_add(event_date_local, interval 30 day) <= o.observed_through' not in result


def test_mature_query_retains_exact_label_definition_and_maturity_gate():
    result = live.adapt_anchor_sql(sql_fixture(), NOW.date(), predictors=False)
    assert 'outcomes as (' in result
    assert 'warranty_signal_within_30d' in result
    assert 'and date_add(event_date_local, interval 30 day) <= o.observed_through' in result


def test_uncorrected_compiled_sql_fails_instead_of_guessing_history_contract():
    with pytest.raises(ValueError, match='history availability'):
        live.adapt_anchor_sql(sql_fixture().replace('h.event_created_ts <= a.event_end_ts', 'true'),
            NOW.date(), predictors=True)


def test_projection_rejects_injected_source_column():
    with pytest.raises(ValueError, match='source column'): live._projection(['bad); SELECT secret'])


def weather(day='2026-09-26'):
    return {'weather_location_id': 'a' * 64, 'weather_date': day, 'precipitation_sum_mm': 3.0,
        'temperature_2m_mean_c': 28.0, 'relative_humidity_2m_mean_pct': 80.0,
        'soil_moisture_0_to_7cm_mean': 0.4}


def test_weather_cannot_fabricate_complete_windows_with_duplicate_observations():
    with pytest.raises(ValueError, match='Duplicate'): live.validate_weather_records([weather(), weather()], NOW.date())


def test_weather_excludes_partial_or_future_dates_and_unknown_grids():
    with pytest.raises(ValueError, match='partial-day'): live.validate_weather_records([weather()], NOW.date().replace(day=25))
    with pytest.raises(ValueError, match='grid identity'):
        live.validate_weather_records([dict(weather(), weather_location_id='untrusted')], NOW.date())


def test_private_live_features_cannot_be_written_outside_outputs(tmp_path):
    with pytest.raises(ValueError, match='ignored outputs'):
        live.derive({}, {}, tmp_path / 'public', now=NOW)


def test_large_source_request_fails_before_contacting_warehouse(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'
    baseline = tmp_path / 'baseline.json'
    baseline.write_text(json.dumps({'metadata': {'snapshot_id': live.replay.OLD_TABLE.split('_')[-1]}}))
    monkeypatch.setattr(live, 'BASELINE', baseline)
    monkeypatch.setattr(live.b, 'ROOT', workspace)
    monkeypatch.setattr(live, 'validate_frozen_source_contract', lambda: '0' * 64)
    monkeypatch.setattr(live, 'build_stages', lambda *args, **kwargs: ([], {'source': 'x' * live.SOURCE_CHUNK_BYTES}, {}))
    with pytest.raises(ValueError, match='bounded request'):
        live.derive({}, {}, workspace / 'outputs/test', now=NOW)


def test_large_positional_sheet_is_chunked_without_loss_or_reordering():
    records = [{'source_sheet_row': index, 'source_column_001': 'x' * 200}
        for index in range(100)]
    chunks = live.source_chunks(records, maximum_bytes=1000)
    assert len(chunks) > 1
    assert [row for chunk in chunks for row in chunk] == records
    assert all(len(json.dumps(chunk, ensure_ascii=False, separators=(',', ':')).encode()) <= 1000
        for chunk in chunks)


def test_single_oversized_sheet_row_fails_closed():
    with pytest.raises(ValueError, match='Single source row'):
        live.source_chunks([{'source_sheet_row': 1, 'source_column_001': 'x' * 200}], maximum_bytes=100)


@requires_private_bundle
def test_exact_frozen_compiled_and_macro_contract_is_current():
    assert len(live.validate_frozen_source_contract()) == 64


@requires_private_bundle
def test_compiled_feature_sql_drift_blocks_live_derivation(tmp_path, monkeypatch):
    pin = json.loads(live.PIN.read_text(encoding='utf-8'))
    pin['compiled_query_hashes']['sales.sql'] = '0' * 64
    corrupt = tmp_path / 'pin.json'
    corrupt.write_text(json.dumps(pin))
    monkeypatch.setattr(live, 'PIN', corrupt)
    with pytest.raises(ValueError, match='Compiled live feature SQL'):
        live.validate_frozen_source_contract()


@requires_private_bundle
def test_canonical_anchor_macro_hash_wins_over_older_windows_key(tmp_path, monkeypatch):
    source = live.b.ROOT
    registry = json.loads((source/'config/cp2_model_current.json').read_text(encoding='utf-8'))
    for path in ['config/cp2_model_current.json',
            registry['bundle_relative_path']+'/bundle.json',
            'dbt/macros/calendar_history_available.sql',
            'dbt/macros/calendar_snapshot_observation_sql.sql',
            'dbt/macros/warranty_anchor_dataset_sql.sql']:
        destination = tmp_path/path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/path, destination)
    # The legacy backslash key in the bundle names a different pre-fix hash.
    # A source rewrite to that version must not be accepted as current.
    macro = tmp_path/'dbt/macros/warranty_anchor_dataset_sql.sql'
    macro.write_text('obsolete macro content', encoding='utf-8')
    monkeypatch.setattr(live.b, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='Frozen dbt macro'):
        live.validate_frozen_source_contract()


def test_exact_address_reuse_only_exposes_conservative_hashes():
    description = ('Nama: Example\nAlamat: No 13 Jalan Frekuensi U16/133, Elmina East, '
        '40160 Shah Alam, Selangor\nPhone: 0126611565')
    extracted = 'No 13 Jalan Frekuensi U16/133, Elmina East, 40160 Shah Alam, Selangor'
    rows = [{'calendar_event_row': -25, 'description': description,
        'description_text': description, 'location': '', 'extracted_line': extracted}]
    result = live.exact_address_hash_candidates(rows)
    assert len(result) == 1 and result[0]['calendar_event_row'] == -25
    assert len(result[0]['address_hash']) == 64
    assert 'Jalan' not in repr(result) and '0126611565' not in repr(result)


def test_address_reuse_rejects_contact_or_ambiguous_grain():
    contact = {'calendar_event_row': -30, 'description': None,
        'description_text': '', 'location': 'Contact 0126611565', 'extracted_line': None}
    assert live.exact_address_hash_candidates([contact]) == []
    with pytest.raises(ValueError, match='candidate grain'):
        live.exact_address_hash_candidates([contact, contact])
    with pytest.raises(ValueError, match='candidate grain'):
        live.exact_address_hash_candidates([dict(contact, calendar_event_row=1)])


def test_geocode_reuse_sql_rejects_coordinate_tier_conflicts_and_edited_old_rows():
    sql = live.geocode_reuse_sql('`project`.`quality`.`calendar_event_geocodes_all_v2`')
    assert 'COUNT(DISTINCT TO_JSON_STRING(STRUCT(latitude, longitude, precision_tier))) = 1' in sql
    assert 'calendar_event_row NOT IN UNNEST(@invalid_geocodes)' in sql
    assert 'exact_address_hash_reuse_not_verified_property' in sql
    assert 'manual_override_protected' in sql
    assert '@address_candidates' in sql


def test_address_extraction_query_uses_original_geocoder_expression():
    sql = live.address_candidate_sql()
    expression = live._address_tools().calendar_address_expr('e.description_text')
    assert expression in sql
    assert 'live_calendar_raw' in sql and 'live_calendar_events' in sql
    assert 'c.calendar_event_row < 0' in sql
