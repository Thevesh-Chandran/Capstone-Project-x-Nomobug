"""Publish aggregate source evidence and enforce point-in-time admission status."""
from pathlib import Path
import hashlib,json
import pandas as pd
from scripts.collect_food_outlet_coverage import ROOT,OUT
from scripts.simplify_supervisor_review import OUT as REVIEW
from scripts.build_supervisor_model_review import markdown

def main():
    food=json.loads((OUT/'food_coverage_summary.json').read_text());age=json.loads((OUT/'building_date_coverage_summary.json').read_text())
    sources=json.loads((OUT/'source_catalog.json').read_text())
    before=json.loads((ROOT/'outputs/model_validation/20261017_predictor_value/protocol.json').read_text())['frozen_hashes']
    folder=ROOT/'outputs/cp2-v2/prospective_callback_v2'
    assert all(hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest for name,digest in before.items())
    assert food['sampled_locations']==1127 and food['successful_requests']==1127 and food['failed_requests']==0
    admission={'checked_local_date':'2026-10-17','food_locations_collected':1127,'nearby_food_locations':781,'capped_counts':1,'building_locations_checked':100,'building_searches_capped':40,'verified_building_ages':0,'historically_admissible_new_predictor_rows':0,'candidate_training_run':False,'reason':'Historical food opening/closing dates unverified; no verified construction dates/building identities; facility coordinates, operating dates and inventory incomplete; no verified general building pest registry. Do not fit guessed values.','frozen_hashes_unchanged':True}
    (OUT/'model_admission_decision.json').write_text(json.dumps(admission,indent=2))
    for name in ['source_catalog.json','food_coverage_summary.json','building_date_coverage_summary.json','model_admission_decision.json','public_facility_candidates.csv']:
        (REVIEW/'data'/name).write_bytes((OUT/name).read_bytes())
    sections=[('New predictor sources — actual findings','17 October 2026. Existing model weights, thresholds and future-test receipts are unchanged.'),
      ('Food outlets','All 1,127 locations in the archived environmental cache were queried successfully. 781 have mapped food places within 500 metres. One response reached the result limit, making that count a lower bound. This covers the cache, not every current customer. Zero mapped places does not prove none exist. These are mapped objects, not a verified business census or hygiene assessment.'),
      ('Building age','The 100-location coverage check returned no construction-date tags in the inspected records. Forty results were capped. This is not proof dates are unavailable elsewhere. Nearby building points cannot verify which building a customer occupies; an opening date may refer to the business rather than construction. Verified building ages obtained: zero.'),
      ('Treatment facilities','Four named public IWK facility candidates were catalogued. Their coordinates and operating dates still need verification. Offices and payment counters must not be counted as treatment plants. Air Selangor’s 2022 report provides a named drinking-water plant inventory and regional map; precise geometry is still needed. Sewage treatment and drinking-water treatment are separate features. IWK’s official asset portal advertises paid access; no purchase was made.'),
      ('Past pest history','iDengue is a potential official mosquito/dengue-context source. It cannot substitute for general building cockroach, rodent or all-pest history. No verified general building pest-history dataset was obtained.'),
      ('Can these improve the model yet?','Not established. Zero new predictor rows have confirmed point-in-time eligibility for the historical training dates. Today’s food map cannot be presented as the map surrounding a 2024 service. No model was fitted with guessed building ages or undated histories. The completed 93-input removal tests remain separate. Existing static environmental inputs also need as-of-date provenance review before strong historical claims.'),
      ('Access failures','The Overpass primary and mirror POST requests returned 502/500; small GET probes returned 406/429. These failed downloads were not converted into zero features. The existing Geoapify connection successfully provided food and building-coverage observations.'),
      ('Remaining work','Verify historical dates, exact building/facility identity, customer-location precision, facility coverage and duplicate businesses. Then compare any admissible new inputs on consistent chronological validation periods. The frozen prospective test remains unchanged. No new accuracy improvement is claimed.')]
    text='\n\n'.join(('# ' if i==0 else '## ')+title+'\n'+body for i,(title,body) in enumerate(sections))
    text+='\n\n## Source catalog\n'
    for row in sources:text+=f"\n[{row['source']}]({row['url']}) — {row['predictor']}: {row['status']}.\n"
    (OUT/'SOURCE_FINDINGS.md').write_text(text,encoding='utf-8')
    page='<!doctype html><meta charset="utf-8"><title>New predictor sources</title><style>body{max-width:980px;margin:40px auto;padding:0 24px;font:16px/1.7 Arial;color:#172554}h1{font-size:32px}h2{margin-top:32px}a{color:#2563eb}</style>'+markdown(text)
    (OUT/'SOURCE_FINDINGS.html').write_text(page,encoding='utf-8');(REVIEW/'New_Predictor_Sources.html').write_text(page,encoding='utf-8')
    print('Verified counts, source evidence, historical-admission gate and unchanged frozen hashes. No private customer cache exported.')

if __name__=='__main__':main()
