import pandas as pd

from scripts import benchmark_warranty_models as b
from scripts.compare_2026_training import partitions, development_splits, FINAL_START


def frame_fixture():
    rows = []
    for i, date in enumerate(pd.date_range('2025-10-01', '2026-08-14').repeat(2)):
        rows.append({'population': 'callback', 'sales_record_id': str(i),
                     'address_hash': str(i), 'validation_group': str(i),
                     'anchor_date': date, 'outcome_end_date': date+pd.Timedelta(days=30),
                     b.TARGET: i % 4 == 0})
    return pd.DataFrame(rows)


def test_mature_labels_and_global_final_property_purge():
    frame = frame_fixture()
    frame.loc[frame.anchor_date.eq('2026-01-05'), ['validation_group','address_hash']] = 'shared'
    frame.loc[frame.anchor_date.eq('2026-07-05'), ['validation_group','address_hash']] = 'shared'
    for recent in (False, True):
        train, test, _ = partitions(frame, recent)
        assert train.outcome_end_date.lt(FINAL_START).all()
        assert not train.anchor_date.ge('2026-06-01').any()
        assert 'shared' not in set(train.validation_group)
        assert set(train.validation_group).isdisjoint(test.validation_group)
        if recent:
            assert train.anchor_date.ge('2026-01-01').all()


def test_regimes_have_identical_final_cohort_and_nested_training():
    frame = frame_fixture()
    all_train, test, _ = partitions(frame, False)
    recent, recent_test, _ = partitions(frame, True)
    pd.testing.assert_frame_equal(test, recent_test)
    assert set(recent.sales_record_id) < set(all_train.sales_record_id)


def test_development_validation_outcomes_known_before_final_fit():
    train, test, _ = partitions(frame_fixture(), True)
    folds = development_splits(train)
    assert len(folds) == 3
    for _, past, validation, _ in folds:
        assert past.outcome_end_date.lt(validation.anchor_date.min()).all()
        assert validation.outcome_end_date.lt(FINAL_START).all()
        assert set(past.validation_group).isdisjoint(validation.validation_group)
        assert set(validation.validation_group).isdisjoint(test.validation_group)
