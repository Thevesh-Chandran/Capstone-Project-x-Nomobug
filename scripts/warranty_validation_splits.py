"""Time and group separation for retrospective warranty experiments."""
import pandas as pd


def connected_validation_groups(frame, sales_column='sales_record_id',
                                property_column='address_hash'):
    """Keep every linked package and property in one deterministic component.

    A package can have several property hashes, including missing locations. A
    property can link several packages. Per-row property-or-package fallback
    fails to keep those transitive connections together.
    """
    packages = frame[sales_column].astype('string').str.strip()
    if packages.isna().any() or packages.eq('').any():
        raise ValueError('Connected validation grouping requires package identifiers')
    properties = (frame[property_column].astype('string').str.strip()
                  if property_column in frame else pd.Series(pd.NA, index=frame.index,
                                                             dtype='string'))
    parent = {}

    def find(node):
        parent.setdefault(node, node)
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != node:
            previous = parent[node]
            parent[node] = root
            node = previous
        return root

    for package, property_id in zip(packages, properties):
        package_node = 'package:' + package
        package_root = find(package_node)
        if pd.notna(property_id) and property_id != '':
            property_root = find('property:' + property_id)
            if package_root != property_root:
                # Stable union order also avoids data-row-order dependence.
                lower, upper = sorted((package_root, property_root))
                parent[upper] = lower
    members = {}
    for node in list(parent):
        members.setdefault(find(node), []).append(node)
    labels = {}
    for root, nodes in members.items():
        property_nodes = [node for node in nodes if node.startswith('property:')]
        labels[root] = min(property_nodes or nodes)
    return pd.Series([labels[find('package:' + package)] for package in packages],
                     index=frame.index, name='validation_group', dtype='string')


def assert_package_property_disjoint(train, test):
    """Assert the two independent identifiers cannot cross an evaluation split."""
    if 'sales_record_id' in train and 'sales_record_id' in test:
        assert set(train['sales_record_id']).isdisjoint(test['sales_record_id']), \
            'A package occurs in both training and evaluation'
    if 'address_hash' in train and 'address_hash' in test:
        train_properties = train['address_hash'].astype('string').str.strip()
        test_properties = test['address_hash'].astype('string').str.strip()
        train_properties = set(train_properties.dropna()) - {''}
        test_properties = set(test_properties.dropna()) - {''}
        assert train_properties.isdisjoint(test_properties), \
            'A property occurs in both training and evaluation'


def purged_forward_split(frame, start, end, horizon_days=30):
    dates = pd.to_datetime(frame['prediction_anchor_date'])
    outcome_end = dates + pd.to_timedelta(horizon_days, unit='D')
    test = frame[(dates >= pd.Timestamp(start)) & (dates < pd.Timestamp(end))].copy()
    train = frame[outcome_end < pd.Timestamp(start)].copy()
    if 'sales_record_id' in frame.columns:
        groups = connected_validation_groups(frame)
        test_groups = set(groups.loc[test.index])
        train = train[~groups.loc[train.index].isin(test_groups)].copy()
        assert_package_property_disjoint(train, test)
    return train, test
