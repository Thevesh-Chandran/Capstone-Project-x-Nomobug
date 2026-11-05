"""Build a local, source-backed map interaction preview (not a production release)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/portal_acceptance/20261015/runtime'
DEST = ROOT / 'outputs/dashboard_design/current_spatial_preview'

def main():
    business = json.loads((SOURCE / 'business_tools_private.json').read_text())
    model = json.loads((SOURCE / 'area_rows_private.json').read_text())
    boundaries = json.loads((SOURCE / 'district_boundaries_public.json').read_text())
    sales = [dict(r['location'], date=r['date'], amount=r['sales_rm'], id=r['sale_id'],
                  customer=r['customer_key'], programme=r['programme_id'],
                  package=r['package'], pest=r['pest'])
             for r in business['records']['sales'] if r.get('location')]
    visits = [dict(r['location'], date=r['date'], pest=r['pest'])
              for r in business['records']['appointments']
              if r.get('location') and r.get('warranty_signal')]
    payload = {'sales': sales, 'visits': visits, 'model': model, 'boundaries': boundaries,
               'sales_total': len(business['records']['sales']),
               'visit_total': sum(bool(r.get('warranty_signal')) for r in business['records']['appointments']),
               'source': business['receipt'],
               'snapshot_at': json.loads((SOURCE/'business_snapshot.json').read_text()).get('fetched_at_utc')}
    template = (ROOT / 'templates/spatial_preview.html').read_text(encoding='utf-8')
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'index.html').write_text(template.replace('__REVIEWED_DATA__', json.dumps(payload).replace('</','<\\/')), encoding='utf-8')
    print(json.dumps({'file': str(DEST / 'index.html'), 'located_sales': len(sales),
                      'located_warranty_signals': len(visits), 'evaluated_services': len(model)}))

if __name__ == '__main__':
    main()
