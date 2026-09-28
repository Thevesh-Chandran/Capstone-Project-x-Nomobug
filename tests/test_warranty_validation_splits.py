from datetime import date
import pandas as pd
from scripts.warranty_validation_splits import (
    assert_package_property_disjoint, connected_validation_groups,
    purged_forward_split,
)


def test_forward_split_waits_for_outcome_and_purges_shared_property():
    data = pd.DataFrame({
        'prediction_anchor_date': [date(2025,1,1), date(2025,3,15), date(2025,1,1), date(2025,4,2)],
        'address_hash': ['safe', 'late_label', 'shared', 'shared'],
        'sales_record_id': ['a','b','c','d'],
    })
    train, test = purged_forward_split(data, date(2025,4,1), date(2025,7,1))
    assert train['sales_record_id'].tolist() == ['a']
    assert test['sales_record_id'].tolist() == ['d']


def test_components_connect_multiple_properties_packages_and_missing_locations():
    data = pd.DataFrame({
        'sales_record_id': ['a', 'a', 'b', 'a', 'c', 'c', 'd', 'e'],
        'address_hash': ['north', 'south', 'south', None, None, '', 'west', 'west'],
    })
    groups = connected_validation_groups(data)
    assert groups.iloc[:4].nunique() == 1
    assert groups.iloc[4:6].tolist() == ['package:c', 'package:c']
    assert groups.iloc[6:].nunique() == 1
    assert groups.nunique() == 3
    pd.testing.assert_series_equal(groups, connected_validation_groups(data.iloc[::-1]).sort_index())


def test_forward_split_purges_transitively_connected_packages_and_properties():
    data = pd.DataFrame({
        'prediction_anchor_date': [date(2025,1,1)] * 2 + [date(2025,4,2)]
                                 + [date(2025,1,1), date(2025,4,3)]
                                 + [date(2025,1,1)] * 2,
        'sales_record_id': ['a', 'b', 'a', 'safe', 'd', 'd', 'e'],
        'address_hash': ['north', 'north', 'south', 'safe', 'west', None, 'west'],
    })
    train, test = purged_forward_split(data, date(2025,4,1), date(2025,7,1))
    assert train['sales_record_id'].tolist() == ['safe']
    assert test['sales_record_id'].tolist() == ['a', 'd']
    assert_package_property_disjoint(train, test)


def test_components_reject_missing_package_identifiers():
    import pytest
    with pytest.raises(ValueError, match='package identifiers'):
        connected_validation_groups(pd.DataFrame({
            'sales_record_id': ['a', None], 'address_hash': ['same', 'same'],
        }))


def test_disjoint_assertion_detects_each_independent_identifier():
    import pytest
    train = pd.DataFrame({'sales_record_id': ['a'], 'address_hash': ['north']})
    with pytest.raises(AssertionError, match='package'):
        assert_package_property_disjoint(train, pd.DataFrame({
            'sales_record_id': ['a'], 'address_hash': ['south'],
        }))
    with pytest.raises(AssertionError, match='property'):
        assert_package_property_disjoint(train, pd.DataFrame({
            'sales_record_id': ['b'], 'address_hash': ['north'],
        }))
