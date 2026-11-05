import pytest
from scripts.evaluate_matured_cp2_subset import is_mature,check_entry
from scripts import freeze_callback_prospective as p
from pathlib import Path

def test_full_thirty_calendar_days_required():
    assert not is_mature('2026-10-01','2026-10-30')
    assert is_mature('2026-10-01','2026-10-31')
    assert not is_mature('2026-10-16','2026-10-31')

def test_changed_receipt_rejected_before_scoring():
    with pytest.raises(ValueError,match='hash changed'):
        check_entry({'record_sha256':'wrong'},{},Path('.'))

def test_changed_bundle_rejected(monkeypatch):
    monkeypatch.setattr(p,'digest',lambda _: 'expected')
    entry={'bundle_sha256':'altered'};entry['record_sha256']=p.record_digest(entry)
    with pytest.raises(ValueError,match='bundle differs'):
        check_entry(entry,{},Path('.'))

def test_outcome_cannot_enter_receipt(monkeypatch):
    monkeypatch.setattr(p,'digest',lambda _: 'expected')
    entry={'bundle_sha256':'expected','schema_version':2,'source_receipt':{'source':p.SOURCE_NAME},'row':{p.b.TARGET:False}}
    entry['record_sha256']=p.record_digest(entry)
    with pytest.raises(ValueError,match='includes outcome'):
        check_entry(entry,{},Path('.'))
