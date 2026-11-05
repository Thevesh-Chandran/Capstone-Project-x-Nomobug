from scripts.audit_model_outcome_sample import assess_event

def test_cancelled_sequence_is_not_supported_return():
    assert assess_event({'summary':'CANCELLED GPC 4/3','status':'confirmed'})=='schedule_change_needs_review'
    assert assess_event({'summary':'WARRANTY','status':'cancelled'})=='schedule_change_needs_review'

def test_paid_stage_does_not_become_extra_visit():
    assert assess_event({'summary':'GPC 3/3','status':'confirmed'})=='within_paid_sequence_needs_review'
    assert assess_event({'summary':'GPC 4/3','status':'confirmed'})=='beyond_paid_sequence_needs_review'

def test_complimentary_kept_separate():
    assert assess_event({'summary':'GPC Complimentary','status':'confirmed'})=='free_visit_needs_review'
