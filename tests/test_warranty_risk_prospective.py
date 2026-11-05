import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import warranty_risk_prospective as wp  # noqa: E402


def _appt(d, warranty=False, lat=3.1):
    return {'date': d, 'warranty_signal': warranty, 'district': 'Selangor / Petaling', 'location': {'latitude': lat, 'longitude': 101.6, 'uncertainty_km': 1.0}}


def _write(folder, appts):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'business_tools_private.json').write_text(json.dumps({'customers': [], 'records': {'appointments': appts, 'sales': []}}))
    return folder


def test_freeze_then_evaluate_counts_only_later_warranty_visits(tmp_path):
    first = _write(tmp_path / 'a', [_appt('2025-10-10', lat=3.1), _appt('2025-10-12', lat=3.2), _appt('2025-10-20')])
    frozen = wp.freeze(first, tmp_path / 'out')
    rec = json.loads(frozen.read_text())
    assert rec['windows'] == 2 and all('property' in r and 'name' not in r for r in rec['rows'])
    with pytest.raises(SystemExit):
        wp.evaluate(frozen, first)  # same snapshot is refused
    later = _write(tmp_path / 'b', [_appt('2025-10-10', lat=3.1), _appt('2025-10-12', lat=3.2), _appt('2025-10-20'),
                                    _appt('2025-11-01', True, lat=3.2), _appt('2025-12-30')])
    res = wp.evaluate(frozen, later)
    assert res['matured_windows'] == 2 and res['complete'] and res['warranty_visits'] == 1
