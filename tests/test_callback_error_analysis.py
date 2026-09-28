import numpy as np
import pytest
from scripts.analyze_callback_errors import classify_errors, top_budget, evidence_flags


def event(day, reason='post_package_sequence'):
    return dict(days_after_anchor=day, is_callback=True, reason=reason,
                label_provenance='automatic', same_property_hash=True,
                geocode_distance_m=None, anchor_uncertainty_m=None,
                return_uncertainty_m=None, event_category='warranty', review_status='Not reviewed')


def test_confusion_at_threshold_boundary():
    assert classify_errors([1,1,0,0], [.12,.119,.12,.1], .12).tolist()==['TP','FN','FP','TN']


def test_budget_keeps_boundary_ties():
    assert top_budget([.9,.8,.8,.1,.0], .4).tolist()==[True,True,True,False,False]
    with pytest.raises(ValueError):
        top_budget([np.nan])


def test_day_30_positive_and_day_31_later_evidence():
    flags=evidence_flags(dict(following_events=[event(30),event(31)], dated_claim_record_count=1))
    assert flags['callback_events_30d']==1
    assert flags['later_callback_31_60d']
    assert not flags['dated_claim_record_without_calendar_callback']


def test_claim_record_is_not_automatically_calendar_target():
    flags=evidence_flags(dict(following_events=[event(31)], dated_claim_record_count=1))
    assert not flags['reconstructed_target']
    assert flags['dated_claim_record_without_calendar_callback']


def test_manual_confirmation_is_separate_from_sequence_provenance():
    callback=event(1,'manual_review_confirmed_warranty')
    callback['label_provenance']='manual_review_2026_09_27'
    flags=evidence_flags(dict(following_events=[callback], dated_claim_record_count=0))
    assert flags['manual_review_positive']
    assert not flags['post_package_only_positive']


def test_distance_requires_uncertainty_evidence():
    callback=event(2)
    callback['geocode_distance_m']=5000
    assert not evidence_flags(dict(following_events=[callback], dated_claim_record_count=0))['distant_location_positive']
    callback.update(anchor_uncertainty_m=100,return_uncertainty_m=100)
    assert evidence_flags(dict(following_events=[callback], dated_claim_record_count=0))['distant_location_positive']
