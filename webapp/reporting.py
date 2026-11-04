"""Aggregate-only reporting payload; all customer identity remains in the portal."""
from collections import Counter
from webapp.business import aggregate


def build(value, snapshot):
    report = aggregate(value['records'])
    statuses = Counter()
    seen = set()
    for customer in value.get('customers', []):
        for c in customer.get('contracts', []):
            identity = c.get('sales_record_id')
            if not identity or identity in seen:
                continue
            seen.add(identity)
            total, paid, remaining = (c.get(k) for k in (
                'sale_total_rm', 'sales_total_recorded_paid_rm', 'sales_remaining_balance_rm'))
            if any(x is None for x in (total, paid, remaining)) or total < 0 or paid < 0:
                statuses['Needs checking'] += 1
            elif remaining <= 0 and paid >= total:
                statuses['Fully paid in source'] += 1
            elif remaining > 0 and paid == 0:
                statuses['No payment recorded'] += 1
            elif remaining > 0 and 0 < paid < total:
                statuses['Partly paid in source'] += 1
            else:
                statuses['Needs checking'] += 1
    tables = snapshot.get('tables', {})
    payment_fields = ('billing_arrangement', 'tracker_as_of_date', 'candidate_contract_rows',
                      'recorded_contract_value_rm', 'sales_total_recorded_paid_rm',
                      'positive_recorded_remaining_balance_rm',
                      'contracts_with_scheduled_reminders_next_7_days', 'contracts_without_source_schedule')
    return {
        'sales': report['sales'], 'services': report['services'],
        'coverage': {k: value.get('receipt', {}).get('coverage', {}).get(k)
                     for k in ('sale_rows', 'appointment_rows', 'unassigned_sales', 'unassigned_appointments', 'customer_groups')},
        'payments': [{k: r.get(k) for k in payment_fields} for r in tables.get('payments', [])],
        'payment_status': [{'status': k, 'contracts': v} for k, v in sorted(statuses.items())],
        'freshness': [{k: r.get(k) for k in ('source_name', 'extracted_at_utc', 'release_run_id')}
                      for r in tables.get('freshness', [])],
        'release': value.get('receipt', {}).get('published_release'),
        'built_at_utc': value.get('receipt', {}).get('built_at_utc'),
        'payment_scope': 'Current contract records; month, area and pest filters do not apply. Recorded amounts are not independently verified settlements.',
        'definitions': {'sales': 'Recorded package prices, not cash received or profit.',
                        'visits': 'Calendar bookings, not confirmed completed treatments.',
                        'warranty': 'Recorded warranty signals, not proof of treatment failure.',
                        'reminders': 'Source reminder dates; a past date does not prove overdue debt, payment or a sent reminder.'}}
