import runpy
from pathlib import Path
import pytest

contract = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/prospects_source_contract.py'))
headers = contract['EXPECTED_HEADERS']
validate = contract['validate_headers']

def test_expected_headers():
    validate(headers)

def test_whitespace_only_difference_allowed():
    validate([h.replace(' ', '\n') for h in headers])

@pytest.mark.parametrize('change', ['swap', 'rename', 'extra', 'missing'])
def test_layout_change_stops(change):
    changed = headers.copy()
    if change == 'swap':
        changed[0], changed[1] = changed[1], changed[0]
    elif change == 'rename':
        changed[12] = 'MESSAGE DATE'
    elif change == 'extra':
        changed.append('new field')
    else:
        changed.pop()
    with pytest.raises(SystemExit):
        validate(changed)
