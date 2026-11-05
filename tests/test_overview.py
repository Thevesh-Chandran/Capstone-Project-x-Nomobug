from datetime import date

from webapp import overview


def sale(key, customer, programme, day, package, rm=500.0, district='Selangor / Petaling', premise='RESIDENTIAL', pest='Cockroach'):
    return {'sale_key': key, 'customer_key': customer, 'programme_id': programme, 'date': day, 'package': package,
            'sales_rm': rm, 'district': district, 'premise': premise, 'pest': pest}


def test_package_families_cover_the_sheet_labels():
    f = overview.package_family
    assert f('GPC3x (AF1) + Semut') == 'Home programme, 3 to 6 visits'
    assert f('GPC1x') == 'Home, single visit'
    assert f('PROMO399') == 'Home promotion package'
    assert f('GPC429') == 'Home promotion package'
    assert f('B2B12x + 3 FREE') == 'Business contract, monthly (12+ visits)'
    assert f('B2B 6x') == 'Business contract, 3 to 6 visits'
    assert f('B2B1x') == 'Business, 1 to 2 visits'
    assert f('Termite Consultation') == 'Consultation or inspection'
    assert f('2 TBS + GPC 3x') == 'Termite baiting (TBS)'
    assert f('Unspecified') == f(None) == 'Not recorded'
    assert f('Misting Add On') == 'Other or add-on'


def test_package_scorecard_counts_returning_customers_and_trend():
    sales = [sale(f's{i}', f'c{i}', f'p{i}', '2026-09-01', 'GPC3x') for i in range(12)]
    # c0 bought an earlier programme, so its September sale is a returning-customer sale
    sales.append(sale('old', 'c0', 'p-old', '2026-03-01', 'Unspecified'))
    sales += [sale(f'x{i}', 'cx', 'px', '2026-09-01', 'GPC1x') for i in range(3)]  # too few to show
    value = {'records': {'sales': sales}, 'customers': [
        {'customer_key': k, 'identity_status': 'exact_name_and_phone'} for k in [f'c{i}' for i in range(12)] + ['cx']]}
    result = overview.packages(value, date(2026, 11, 5))
    assert [r['package'] for r in result['rows']] == ['Home programme, 3 to 6 visits']
    row = result['rows'][0]
    assert row['sales'] == 12 and row['average_rm'] == 500
    assert row['returning_share'] == 1 / 12
    assert row['last_quarter'] == 12 and row['change'] is None
    assert result['recorded_sales'] == 15
    assert result['by_job'][0]['usual_package'] == 'Home programme, 3 to 6 visits'


def test_unreliable_identities_never_count_as_returning():
    sales = [sale('a', 'k', 'p1', '2026-03-01', 'GPC3x'), sale('b', 'k', 'p2', '2026-09-01', 'GPC3x')]
    value = {'records': {'sales': sales}, 'customers': [{'customer_key': 'k', 'identity_status': 'needs_review'}]}
    assert overview._returning(sales, value['customers']) == set()


def test_areas_compare_twelve_months_and_skip_unknown_addresses():
    sales = [sale(f'n{i}', f'c{i}', f'p{i}', '2026-06-01', 'GPC3x', rm=1000) for i in range(20)]
    sales += [sale(f'o{i}', f'c{i}', f'q{i}', '2025-06-01', 'GPC3x', rm=500) for i in range(20)]
    sales.append(sale('u', 'cu', 'pu', '2026-06-01', 'GPC3x', district='Unassigned'))
    visits = [{'date': '2026-05-01', 'district': 'Selangor / Petaling', 'warranty_signal': i < 6} for i in range(30)]
    value = {'records': {'sales': sales, 'appointments': visits}, 'customers': []}
    result = overview.areas(value, date(2026, 11, 5))
    top = result['top'][0]
    assert top['area'] == 'Petaling' and top['sales_rm'] == 20000 and top['change'] == 1.0
    assert top['warranty_share'] == 0.2
    assert result['located_share'] == 20 / 21
    assert result['fastest_growing']['area'] == 'Petaling'
