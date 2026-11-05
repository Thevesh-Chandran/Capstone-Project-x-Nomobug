from datetime import date

from webapp import warranty_risk


def _appt(d, warranty=False, lat=3.1, lon=101.6):
    return {'date': d, 'warranty_signal': warranty, 'district': 'Selangor / Petaling', 'location': {'latitude': lat, 'longitude': lon, 'uncertainty_km': 1.0}}


def test_history_features_use_only_earlier_visits():
    prior = [(date(2026, 1, 1), False), (date(2026, 6, 1), True)]
    f = warranty_risk.history_features(prior, date(2026, 7, 1))
    assert f['n_prior'] == 2 and f['n_prior_warranty'] == 1 and f['prior_warranty_rate'] == 0.5
    assert f['warranty_last_90d'] == 1 and f['days_since_last'] == 30 and f['first_visit'] == 0
    assert warranty_risk.history_features([], date(2026, 7, 1))['days_since_last'] == 999


def test_scores_are_probabilities_and_history_raises_risk():
    model = warranty_risk.load()
    quiet = warranty_risk.score(warranty_risk.history_features([], date(2026, 7, 1)), model)
    noisy = warranty_risk.score(warranty_risk.history_features(
        [(date(2026, m, 1), m % 2 == 0) for m in range(1, 7)], date(2026, 7, 1)), model)
    assert 0 < quiet < 1 and 0 < noisy < 1 and noisy > quiet


def test_open_windows_skip_properties_with_a_recorded_warranty_visit():
    value = {'customers': [], 'records': {'appointments': [
        _appt('2026-10-20'), _appt('2026-10-25', True),                 # window already has a warranty visit
        _appt('2026-10-21', lat=3.2), _appt('2026-08-01', lat=3.2),     # open window, one earlier visit
        _appt('2026-07-01', lat=3.3),                                   # outside the 30-day window
    ]}}
    w = warranty_risk.open_windows(value, as_of=date(2026, 10, 28))
    assert w['open_windows'] == 1
    row = w['properties'][0]
    assert row['last_service'] == '2026-10-21' and row['prior_visits'] == 1 and row['days_left'] == 23
    assert 0 < row['risk'] < 1 and w['expected_calls'] == round(row['risk'], 1)
