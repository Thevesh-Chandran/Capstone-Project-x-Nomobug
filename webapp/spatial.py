"""Staff-only map payloads from checked runtime snapshots, without risk scores."""
import math
from webapp.geography import metrics


def location(value):
    if not isinstance(value, dict):
        return None
    lat, lon, uncertainty = (value.get(k) for k in ('latitude', 'longitude', 'uncertainty_km'))
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
               for v in (lat, lon, uncertainty)):
        return None
    if not (.5 <= lat <= 7.6 and 99 <= lon <= 120 and uncertainty >= 0):
        return None
    return dict(latitude=lat, longitude=lon, uncertainty_km=uncertainty)


def payload(business, snapshot, evaluated, boundaries):
    sales, visits, model = [], [], []
    for row in business['records']['sales']:
        point = location(row.get('location'))
        if point:
            sales.append(dict(point, date=row['date'], amount=row['sales_rm'], id=row['sale_id'],
                              customer=row['customer_key'], programme=row['programme_id'],
                              package=row['package'], pest=row['pest'], district=row.get('district','Unassigned')))
    for row in business['records']['appointments']:
        point = location(row.get('location'))
        if point and row.get('warranty_signal'):
            visits.append(dict(point, date=row['date'], pest=row['pest'], district=row.get('district','Unassigned')))
    for row in evaluated:
        point = location(row)
        if point:
            # Only the saved threshold decision is needed to reconcile aggregate
            # historical metrics. Do not deliver experimental risk probabilities.
            model.append(dict(point, score=int(row['score'] >= row['threshold']),
                              threshold=.5, outcome=int(row['outcome'])))
    return {'sales': sales, 'visits': visits, 'model': model, 'boundaries': boundaries,
            'sales_total': len(business['records']['sales']),
            'visit_total': sum(bool(r.get('warranty_signal')) for r in business['records']['appointments']),
            'model_total': len(evaluated), 'source': business['receipt'],
            'model_summary': metrics(evaluated),
            'unlocated_sales_dates': [r['date'] for r in business['records']['sales'] if not location(r.get('location'))],
            'unlocated_visit_dates': [r['date'] for r in business['records']['appointments'] if r.get('warranty_signal') and not location(r.get('location'))],
            'snapshot_at': snapshot.get('fetched_at_utc')}
