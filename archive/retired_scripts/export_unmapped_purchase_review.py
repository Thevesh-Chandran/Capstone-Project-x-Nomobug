"""Private, read-only address-review export at the map's purchase grain."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import html,json
from google.cloud import bigquery
from webapp.data import PROJECT,MAX_BYTES,json_default
from webapp.spatial import location
from scripts.cp2_geocoding import load_cache,address_key,MAP_TIERS,sales_cache_record,clean_sales_address

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/address_review/20261017'

def main(folder=None):
    global OUT
    if folder:
        OUT=Path(folder).resolve()
        if not OUT.is_relative_to(ROOT/'outputs'):raise ValueError('Private review must stay in ignored outputs')
    records=json.loads((OUT/'business_records_private.json').read_text())
    receipt=json.loads((OUT/'business_receipt.json').read_text());prefix=receipt['published_release']
    client=bigquery.Client(project=PROJECT,location='asia-southeast1')
    sql=f'SELECT sales_row_id,sales_record_id,customer_name_raw,address_raw FROM `{PROJECT}.{prefix}_silver.sales`'
    dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False))
    if (dry.total_bytes_processed or 0)>MAX_BYTES:raise ValueError('Query exceeds 100 MiB')
    job=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES))
    raw={str(r['sales_row_id']):dict(r.items()) for r in job.result(timeout=120)}
    cache=load_cache(client);client.close()
    purchases=[r for r in records['sales'] if str(r.get('date') or '').startswith('2026-')]
    missing=[r for r in purchases if not location(r.get('location'))]
    rows=[]
    for sale in missing:
        source=raw.get(sale['sale_key'])
        if not source:raise ValueError('Missing source row')
        address=source.get('address_raw') or ''
        entry=sales_cache_record(cache,address) if address.strip() else None
        status=entry.get('status') if entry else None;tier=entry.get('precision_tier') if entry else None
        if not address.strip():reason='Address missing';action='Provide the full service address.'
        elif not clean_sales_address(address):reason='No usable address text';action='Provide a service address or a clear building/location name.'
        elif not entry:reason='Lookup pending';action='Queued lookup; review address spelling and completeness if it remains unmapped.'
        elif status=='accepted' and tier not in MAP_TIERS:reason='Location too broad';action='Confirm street, building/unit, postcode and town; current result is too broad for the map.'
        elif status in ('review','manual_review','needs_review'):reason='Location needs checking';action='Confirm the actual service address; the result is ambiguous.'
        elif status in ('no_result','not_found'):reason='Address not found';action='Check spelling and provide postcode/town or a map link.'
        elif status=='error':reason='Lookup failed';action='Automatic retry/source investigation needed; no correction inferred.'
        else:reason='Map eligibility needs checking';action='Check location precision and linkage; cache status alone does not establish a usable map point.'
        rows.append({'Sale ID':sale['sale_id'],'Customer':source.get('customer_name_raw') or 'Name missing','Sale date':sale['date'],
          'Address in Sales':address,'Package':sale['package'],'Reason':reason,'Next step':action,
          'Lookup status':status or 'No saved match','Location precision':tier or 'Unknown'})
    rows.sort(key=lambda r:(r['Reason'],r['Customer'].casefold(),r['Sale ID']))
    assert len(rows)==len(missing) and len({r['Sale ID'] for r in rows})==len(rows)
    result={'created_utc':datetime.now(timezone.utc).isoformat(),'source_release':prefix,'scope':'2026 dated purchases; same spatial.location rule as website map','total_purchases':len(purchases),'mapped_purchases':len(purchases)-len(rows),'unmapped_purchases':len(rows),'reasons':dict(Counter(r['Reason'] for r in rows)),'source_job_id':job.job_id,'source_bytes_processed':job.total_bytes_processed,'limitation':'Lookup cache checked at export time; published map rows are pinned to the recorded release. Review file only; no source or map edits.'}
    (OUT/'unmapped_purchase_review_private.json').write_text(json.dumps(rows,default=json_default,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'review_receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    esc=lambda value:html.escape(str(value))
    columns=['Sale ID','Customer','Sale date','Address in Sales','Package','Reason','Next step']
    body=''.join('<tr>'+''.join('<td>'+esc(r[c])+'</td>' for c in columns)+'</tr>' for r in rows)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unmapped purchases — address review</title><style>body{margin:32px;font:15px/1.5 Arial;color:#172033;background:#f5f7fb}h1{font-size:28px;margin-bottom:8px}.controls{display:flex;gap:12px;margin:22px 0}input,select{font:inherit;padding:11px;border:1px solid #ccd3de;border-radius:7px;background:white}input{width:380px}table{border-collapse:collapse;background:white;width:100%}th{position:sticky;top:0;background:#172554;color:white;text-align:left}td,th{padding:12px;border-bottom:1px solid #e2e8f0;vertical-align:top}td:nth-child(4){min-width:280px}td:last-child{min-width:230px}tbody tr:nth-child(even){background:#f8fafc}.table{overflow:auto;border-radius:8px}small{color:#526077}</style><h1>Unmapped purchases</h1>'''
    page+=f'<p><b>{len(rows)} purchases need mapping</b> out of {len(purchases)} dated in 2026. This is a private review list containing customer addresses.</p><small>Source release: {esc(prefix)}. Addresses are shown as recorded in Sales. Rows are purchases, so one customer may appear more than once.</small>'
    options=''.join('<option>'+esc(reason)+'</option>' for reason in sorted(result['reasons']))
    page+='<div class="controls"><input id="search" placeholder="Search customer, sale ID or address"><select id="reason"><option value="">All reasons</option>'+options+'</select><span id="count"></span></div>'
    page+='<div class="table"><table><thead><tr>'+''.join('<th>'+c+'</th>' for c in columns)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    page+='''<script>const rows=[...document.querySelectorAll('tbody tr')];function filter(){let q=document.getElementById('search').value.toLowerCase(),reason=document.getElementById('reason').value,n=0;rows.forEach(r=>{let show=r.textContent.toLowerCase().includes(q)&&(!reason||r.cells[5].textContent===reason);r.hidden=!show;if(show)n++});document.getElementById('count').textContent=n+' shown'}document.getElementById('search').addEventListener('input',filter);document.getElementById('reason').addEventListener('change',filter);filter()</script></html>'''
    (OUT/'Unmapped_Purchases_Private.html').write_text(page,encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--folder')
    main(parser.parse_args().folder)
