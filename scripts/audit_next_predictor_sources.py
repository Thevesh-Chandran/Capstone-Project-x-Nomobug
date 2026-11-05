"""Read-only availability audit: aggregate counts, never customer-text exports."""
from datetime import datetime,timezone
from pathlib import Path
import csv,json,re
import pandas as pd
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from scripts.reconcile_callback_evidence import structured_mentions,snapshot_known_by_service_end,clean_text
from scripts.research_callback_targets import digest

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261017_next_predictor_sources'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'outputs/cp2-v2/callback_evidence_reconciliation/source_private.json'
    raw=json.loads(source.read_text());anchors=raw['rows']['anchors']
    counters={name:{'mentions':0,'snapshot_known_by_service_end':0} for name in [
        'named_problem_field','named_treatment_method','named_severity_field','explicit_prevention',
        'structured_property_type','structured_property_size','structured_pest_count',
        'structured_product_or_dose','structured_hygiene','structured_access','structured_building_age']}
    hint_patterns={'severity_word_hint':r'\b(?:severe|severity|heavy infestation|teruk|banyak|infested)\b',
      'property_word_hint':r'\b(?:apartment|condominium|condo|flat|terrace|terraced|banglo|bungalow|landed|kedai|restaurant|restoran)\b',
      'access_word_hint':r'\b(?:no access|access denied|cannot access|tak dapat masuk|tidak dapat masuk)\b'}
    hints={k:{'mentions':0,'snapshot_known_by_service_end':0} for k in hint_patterns}
    patterns={
      'structured_property_type':r'^\s*(?:property type|building type|house type|jenis rumah|jenis premis|premise type)\s*:\s*\S',
      'structured_property_size':r'^\s*(?:property size|house size|building size|floor area|sq\.?\s*ft|square feet|keluasan|size)\s*:\s*\S',
      'structured_pest_count':r'^\s*(?:pest count|trap count|roach count|bilangan perosak|jumlah tangkapan)\s*:\s*\d',
      'structured_product_or_dose':r'^\s*(?:product|chemical|active ingredient|dosage|dose|bahan aktif|dos)\s*:\s*\S',
      'structured_hygiene':r'^\s*(?:hygiene|sanitation|cleanliness|kebersihan)\s*:\s*\S',
      'structured_access':r'^\s*(?:access|access problem|blocked access|akses)\s*:\s*\S',
      'structured_building_age':r'^\s*(?:building age|construction year|year built|umur bangunan|tahun bina)\s*:\s*\S'}
    for row in anchors:
        text=clean_text(row.get('description'));m=structured_mentions(row.get('description',''))
        present={'named_problem_field':m['problem_field_present'],'named_treatment_method':m['method_field_present'],
          'named_severity_field':m['severity_field_present'],'explicit_prevention':m['problem_prevention_mentioned']}
        present.update({k:bool(re.search(p,text,re.I|re.M)) for k,p in patterns.items()})
        timely=snapshot_known_by_service_end(row)
        for name,flag in present.items():
            counters[name]['mentions']+=int(flag);counters[name]['snapshot_known_by_service_end']+=int(flag and timely)
        fields=' '.join(m.group(1) for m in re.finditer(r'^\s*(?:problem|pest|masalah|remark|remarks|note|notes)\s*:\s*(.*)$',text,re.I|re.M))
        for name,pattern in hint_patterns.items():
            flag=bool(re.search(pattern,fields,re.I));hints[name]['mentions']+=int(flag)
            hints[name]['snapshot_known_by_service_end']+=int(flag and timely)
    schema={}
    for label,path in [('Calendar',ROOT/'data/raw/calendar/nomobug_calendar_events_all_history.csv'),
                       ('Sales',ROOT/'data/raw/session_payment/SALES.csv')]:
        with path.open(encoding='utf-8-sig',newline='') as handle:
            reader=csv.DictReader(handle);headers=reader.fieldnames;count=sum(1 for _ in reader)
        schema[label]={'path':str(path.relative_to(ROOT)),'sha256':digest(path),'rows':count,'headers':headers}
    calendar=pd.read_csv(ROOT/schema['Calendar']['path'],keep_default_na=False)
    starts=pd.to_datetime(calendar.start,errors='coerce',utc=True);ends=pd.to_datetime(calendar.end,errors='coerce',utc=True)
    schema['Calendar']['named_calendar_rows']=int(calendar.calendar_name.str.strip().ne('').sum())
    schema['Calendar']['positive_scheduled_duration_rows']=int((starts.notna()&ends.notna()&ends.gt(starts)).sum())
    previous=ROOT/'outputs/cp2-v2/service_observation_template_smoke_v1_verified/quality_summary.json'
    observations=json.loads(previous.read_text())
    audit={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':digest(__file__),'archived_anchor_rows':len(anchors),
      'source_exported_at':raw.get('executed_at'),'source_sha256':digest(source),'description_coverage':counters,
      'conservative_free_text_hint_counts':hints,
      'free_text_hint_limit':'Keywords in named Problem/Remark/Note fields only; screening hints, not validated severity, building identity or access labels.',
      'schema_evidence':schema,'structured_observation_template':{'anchors':observations['anchors'],
        'observation_versions':observations['observation_versions'],'outcome_versions':observations['outcome_versions']},
      'limits':['Archived source audit, not a fresh read of every live sheet.',
        'Named-field patterns are conservative and bilingual but incomplete; zero detected fields is not proof no information occurs in free text.',
        'An unchanged snapshot timestamp is only a historical eligibility proxy, not full version history.',
        'A scheduled method or time slot does not confirm treatment actually delivered or time spent.',
        'No new predictor trained, no score improvement claimed, no existing test retuned.']}
    (OUT/'internal_availability.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps({'archived_anchors':len(anchors),'coverage':counters,'observation_versions':observations['observation_versions'],'calendar_headers':schema['Calendar']['headers']},indent=2))
    if (OUT/'historical_food_api_probe.json').exists():
        print('Retained existing dated historical-food API probe');return
    # Public city-centre box, not a customer location; verifies historical-map API availability only.
    params={'bboxes':'101.510,3.070,101.520,3.080','time':'2024-01-01,2025-01-01,2026-01-01',
      'filter':'(amenity=restaurant or amenity=cafe or amenity=fast_food or amenity=food_court) and type:node'}
    endpoint='https://api.ohsome.org/v1/elements/count'
    receipt={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'endpoint':endpoint,'parameters':params,
      'scope':'Public Shah Alam sample box; mapped food POIs, not operating-business census; not linked to customers',
      'long_term_limit':'Official migration docs say v1 retires 30 November 2026; v2 requires a key.'}
    try:
        request=Request(endpoint+'?'+urlencode(params),headers={'User-Agent':'Nomobug-capstone-source-audit/1.0'})
        with urlopen(request,timeout=30) as response:payload=json.load(response)
        receipt.update({'status':'retrieved','response':payload})
    except Exception as exc:
        receipt.update({'status':'request_failed','error_type':type(exc).__name__,
          'http_status':getattr(exc,'code',None),'no_data_assumed_zero':True})
    (OUT/'historical_food_api_probe.json').write_text(json.dumps(receipt,indent=2))
    print('Historical food API probe: '+receipt['status'])

if __name__=='__main__':main()
