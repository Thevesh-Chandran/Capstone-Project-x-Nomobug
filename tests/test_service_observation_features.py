import pytest
import sys

from scripts import prepare_service_observation_features as f


def observation(**updates):
    row = dict(observation_id='test-observation', version='1', base_service_reference='test-service',
               sales_record_id='test-sale', property_id='test-property',
               observed_at='2026-10-01T10:00:00+08:00', recorded_at='2026-10-01T10:01:00+08:00',
               available_at='2026-10-01T10:02:00+08:00', source_reference='test-source-version-1',
               reported_pest_types='cockroach', initial_severity='unknown', severity_rubric_id='unknown',
               evidence_count='0', evidence_count_method='visual_live_pest', inspection_minutes='10',
               treatment_methods='gel_bait|spray', treatment_completed='true', access_problem='false')
    return row | updates


def anchor():
    return dict(base_service_reference='test-service', sales_record_id='test-sale',
                property_id='test-property', prediction_at='2026-10-01T10:05:00+08:00')


def test_asof_selects_original_version_and_excludes_post_prediction_edits():
    original = observation()
    later = observation(version='2', evidence_count='100',
                        recorded_at='2026-10-01T10:06:00+08:00',
                        available_at='2026-10-01T10:07:00+08:00')
    rows, coverage = f.prepare([anchor()], [later, original])
    assert rows[0]['evidence_count'] == 0
    assert rows[0]['treatment_gel_bait'] == rows[0]['treatment_spray'] == 1
    assert rows[0]['treatment_trapping'] == 0
    assert coverage == {'available': 1}
    assert not set(rows[0]) & {'initial_severity', 'reported_pest_types', 'callback_visit_reason',
                             'claim_requested_at', 'sales_record_id', 'property_id'}


def test_late_ingestion_and_missing_records_remain_missing():
    rows, coverage = f.prepare([anchor()], [observation(available_at='2026-10-01T10:06:00+08:00')])
    assert coverage == {'late_only': 1}
    assert rows[0]['observation_available'] == 0
    assert rows[0]['evidence_count'] is None
    rows, coverage = f.prepare([anchor()], [])
    assert coverage == {'missing': 1} and rows[0]['treatment_completed'] is None


@pytest.mark.parametrize('completed', ['unknown', 'false'])
def test_planned_methods_do_not_become_treatments_performed(completed):
    rows, _ = f.prepare([anchor()], [observation(treatment_completed=completed)])
    assert rows[0]['treatment_gel_bait'] is None


def test_unknown_count_is_distinct_from_observed_zero():
    rows, _ = f.prepare([anchor()], [observation(evidence_count='', inspection_minutes='',
                                               evidence_count_method='unknown')])
    assert rows[0]['evidence_count'] is None
    assert rows[0]['inspection_minutes'] is None


@pytest.mark.parametrize('updates', [
    {'recorded_at': '2026-10-01T10:01:00'},
    {'observed_at': '2026-10-01T10:03:00+08:00'},
    {'available_at': '2026-10-01T10:00:00+08:00'},
    {'evidence_count': 'NaN'}, {'evidence_count': '-1'}, {'evidence_count': '1.5'},
    {'evidence_count_method': 'unknown'}, {'inspection_minutes': '0'},
    {'initial_severity': 'high'}, {'treatment_methods': 'unknown|spray'},
    {'treatment_completed': 'yes'}, {'source_reference': ''},
])
def test_invalid_or_unproven_observations_are_rejected(updates):
    with pytest.raises(ValueError):
        f.prepare([anchor()], [observation(**updates)])


def test_linkage_and_version_conflicts_are_rejected():
    with pytest.raises(ValueError, match='Full version history'):
        f.prepare([anchor()], [observation(version='2')])
    with pytest.raises(ValueError, match='conflicts'):
        f.prepare([anchor()], [observation(property_id='different-property')])
    with pytest.raises(ValueError, match='Duplicate record'):
        f.prepare([anchor()], [observation(), observation()])
    with pytest.raises(ValueError, match='increase strictly'):
        f.prepare([anchor()], [observation(), observation(version='2')])
    with pytest.raises(ValueError, match='One observation history'):
        f.prepare([anchor()], [observation(), observation(observation_id='another')])
    with pytest.raises(ValueError, match='Duplicate service anchor'):
        f.prepare([anchor(), anchor()], [])


def test_outcome_reason_validation_never_creates_features():
    row = dict(callback_case_id='test-case', version='1', base_service_reference='test-service',
               callback_event_reference='test-return', claim_requested_at='2026-10-02T10:00:00+08:00',
               callback_scheduled_at='2026-10-05T10:00:00+08:00', callback_completed_at='',
               callback_visit_reason='corrective_callback', recorded_at='2026-10-02T11:00:00+08:00',
               available_at='2026-10-02T11:01:00+08:00', source_reference='test-callback-source')
    f.validate_outcomes([row])
    with pytest.raises(ValueError, match='Actual request/completion'):
        f.validate_outcomes([row | {'callback_completed_at': '2026-10-05T11:00:00+08:00'}])
    with pytest.raises(ValueError, match='Unsupported callback reason'):
        f.validate_outcomes([row | {'callback_visit_reason': 'warranty_assumed'}])
    assert not set(f.FEATURES) & set(row)


def test_blank_templates_validate_without_manufacturing_data():
    for filename in ('cp2_prediction_anchors_v1.csv', 'cp2_service_observations_v1.csv',
                     'cp2_callback_outcomes_v1.csv'):
        assert f.read_csv(f.ROOT / 'templates' / filename, filename) == []


def test_extra_or_incomplete_csv_columns_are_rejected(tmp_path):
    template = 'cp2_prediction_anchors_v1.csv'
    header = (f.ROOT / 'templates' / template).read_text().strip()
    path = tmp_path / 'anchors.csv'
    path.write_text(header + '\nservice,sale,property\n')
    with pytest.raises(ValueError, match='row width'):
        f.read_csv(path, template)
    path.write_text(header + ',customer_phone\n')
    with pytest.raises(ValueError, match='header'):
        f.read_csv(path, template)


def test_cli_refuses_public_or_existing_output_before_reading_data(tmp_path, monkeypatch):
    monkeypatch.setattr(f, 'ROOT', tmp_path)
    for destination in [tmp_path / 'public', tmp_path / 'outputs' / '..' / 'public', tmp_path]:
        monkeypatch.setattr(sys, 'argv', ['prepare', '--anchors-csv', 'missing.csv',
                                        '--observations-csv', 'missing.csv',
                                        '--output-dir', str(destination)])
        with pytest.raises(ValueError, match='new private directory'):
            f.main()
    existing = tmp_path / 'outputs' / 'existing'
    existing.mkdir(parents=True)
    monkeypatch.setattr(sys, 'argv', ['prepare', '--anchors-csv', 'missing.csv',
                                    '--observations-csv', 'missing.csv',
                                    '--output-dir', str(existing)])
    with pytest.raises(ValueError, match='new private directory'):
        f.main()
