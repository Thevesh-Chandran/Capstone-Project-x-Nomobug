"""Server-side geographic evaluation of saved historical predictions.

No fitting, threshold selection, or changes to prospective experiment files.
Exact service coordinates and keys never leave this module's private export.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

KEYS = ('population', 'sales_record_id', 'anchor_date')
TARGET = 'warranty_signal_within_30d'
SOURCE_URL = 'https://raw.githubusercontent.com/dosm-malaysia/data-open/main/datasets/geodata/administrative_2_district.geojson'
TRUSTED_TIERS = {'precise_candidate', 'street_candidate', 'manual_verified', 'area_reference_verified', 'postcode_area_candidate'}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def haversine(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    x = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(x)))

def in_ring(x, y, ring):
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside

def polygons(geometry):
    if geometry['type'] == 'Polygon': return [geometry['coordinates']]
    if geometry['type'] == 'MultiPolygon': return geometry['coordinates']
    raise ValueError('Only Polygon and MultiPolygon boundaries supported')

def contains(geometry, lon, lat):
    return any(in_ring(lon, lat, p[0]) and not any(in_ring(lon, lat, hole) for hole in p[1:]) for p in polygons(geometry))

def edge_distance_km(geometry, lon, lat):
    # Local equirectangular segment distance, conservative extra 100m boundary margin.
    sx = 111.195 * math.cos(math.radians(lat)); sy = 111.195
    result = math.inf
    for polygon in polygons(geometry):
        for ring in polygon:
            for a, b in zip(ring, ring[1:] + ring[:1]):
                ax, ay = (a[0]-lon)*sx, (a[1]-lat)*sy
                bx, by = (b[0]-lon)*sx, (b[1]-lat)*sy
                dx, dy = bx-ax, by-ay
                t = max(0, min(1, -(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx or dy else 0
                result = min(result, math.hypot(ax+t*dx, ay+t*dy))
    return result

def district_for(features, lat, lon, uncertainty_km):
    matches = [f for f in features if contains(f['geometry'], lon, lat)]
    if len(matches) != 1: return None
    f = matches[0]
    if edge_distance_km(f['geometry'], lon, lat) <= uncertainty_km + .1: return None
    return f['properties']['state'] + ' / ' + f['properties']['district']

def wilson(successes, n):
    if not n: return None
    z = 1.959963984540054; p = successes/n; den = 1+z*z/n
    centre = (p+z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0, centre-half), min(1, centre+half)]

def metrics(rows):
    n = len(rows)
    if not n: return {'services': 0, 'status': 'no_evaluated_services'}
    positives = sum(r['outcome'] for r in rows)
    tp = sum(r['outcome'] and r['score'] >= r['threshold'] for r in rows)
    fp = sum(not r['outcome'] and r['score'] >= r['threshold'] for r in rows)
    fn = positives-tp; tn = n-positives-fp
    reviewed = sum(r['global_review'] for r in rows)
    found = sum(r['global_review'] and r['outcome'] for r in rows)
    return {'services': n, 'positive_cases': positives, 'accuracy': (tp+tn)/n,
        'always_no_return_accuracy': (n-positives)/n, 'accuracy_interval': wilson(tp+tn,n),
        'true_positives': tp, 'false_alerts': fp, 'missed_cases': fn,
        'precision': tp/(tp+fp) if tp+fp else None, 'recall': tp/positives if positives else None,
        'recall_interval': wilson(tp,positives), 'globally_reviewed': reviewed,
        'cases_found_in_global_top20': found,
        'status': 'small_sample_exploratory' if positives < 10 or n < 50 else 'exploratory_subgroup',
        'note': 'Same historical predictions and fixed threshold. Review counts use the original global top 20; no local threshold tuning.'}

def build(root: Path, out: Path):
    evidence = root/'config/warranty_new_holdout_v5.json'
    report = json.loads(evidence.read_text())
    inputs = root/'outputs/cp2-v2/source_refresh_20260927/new_mature_holdout/dataset_input.json'
    predictions = root/'outputs/cp2-v2/model_corrected_v5/selected_ap_predictions_private.csv'
    boundaries = root/'data/processed/boundaries/dosm_districts.geojson'
    geocodes = root/'data/processed/geocoding/geoapify_pilot_v17.jsonl'
    if digest(inputs) != report['input_file_sha256']: raise ValueError('Historical input hash mismatch')
    features = json.loads(boundaries.read_text())['features']
    data = json.loads(inputs.read_text())['records']
    key = lambda r: (str(r['population']), str(r['sales_record_id']), str(r['anchor_date'])[:10])
    source = {key(r): r for r in data}
    if len(source) != len(data): raise ValueError('Duplicate historical service keys')
    geo = {}
    for line in geocodes.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        if r['address_hash'] in geo: raise ValueError('Duplicate geocode hash')
        geo[r['address_hash']] = r
    with predictions.open(newline='',encoding='utf-8') as handle: saved = list(csv.DictReader(handle))
    if len(saved) != len(source) or {key(r) for r in saved} != set(source): raise ValueError('Incomplete or duplicate prediction coverage')
    if report['results']['selected_ap']['selection'] != 'et10_leaf5': raise ValueError('Wrong historical model')
    # Replay the original trusted artifact, never the all-history refit that
    # already includes these services. Verify bytes before deserializing pickle.
    model_path=root/'outputs/cp2-v2/model_corrected_v5/selected_ap/historical_model.joblib'
    if digest(model_path)!=report['models_sha256']['selected_ap']:raise ValueError('Historical artifact hash mismatch')
    import joblib
    from scripts import benchmark_warranty_models as benchmark
    from scripts.compare_callback_candidates_v2 import predict_artifact
    artifact=joblib.load(model_path)
    replay=predict_artifact(artifact,benchmark.load_dataset_input(inputs)).to_dict('records')
    actual={key(r):r for r in replay}
    for p in saved:
        if key(p) not in actual or any(abs(float(p[c])-float(actual[key(p)][c]))>1e-10 for c in ('probability','threshold')):
            raise ValueError('Saved historical prediction does not match the original artifact replay')
    ranked = sorted(saved, key=lambda r: (-float(r['probability']), key(r)))
    selected = {key(r) for r in ranked[:20]}
    rows = []; reasons = Counter()
    for p in saved:
        s = source[key(p)]; truth = s[TARGET] in (True,1)
        if str(p[TARGET]).lower() not in (str(truth).lower(),str(int(truth))): raise ValueError('Outcome mismatch')
        score, threshold = float(p['probability']), float(p['threshold'])
        if not (0 <= score <= 1 and 0 <= threshold <= 1): raise ValueError('Invalid probability')
        g = geo.get(s['address_hash'], {}); lat,lon = g.get('latitude'),g.get('longitude')
        uncertainty = s.get('location_uncertainty_radius_m')
        usable = (g.get('precision_tier') in TRUSTED_TIERS and isinstance(lat,(int,float))
            and isinstance(lon,(int,float)) and isinstance(uncertainty,(int,float)) and uncertainty >= 0)
        district = district_for(features, lat, lon, uncertainty/1000) if usable else None
        if district is None: reasons['missing_uncertain_or_boundary_location'] += 1
        rows.append({'score': score, 'threshold': threshold, 'outcome': truth,
            'global_review': key(p) in selected, 'district': district or 'Unassigned',
            'latitude': lat if usable else None, 'longitude':lon if usable else None,
            'uncertainty_km': uncertainty/1000 if usable else None})
    overall = metrics(rows)
    if overall['services'] != 100 or overall['positive_cases'] != 5 or overall['cases_found_in_global_top20'] != 4 or abs(overall['accuracy']-.94)>1e-9:
        raise ValueError('Historical aggregate no longer reconciles')
    summary = {'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'cohort':'15–27 August 2026; retrospective held-out services', 'model':'ExtraTrees v5 historical fit',
        'purpose':'Exploratory subgroup analysis of an already inspected historical test; not a new independent evaluation.',
        'overall':overall, 'unassigned_reasons':dict(reasons), 'districts':[],
        'provenance':{str(p.relative_to(root)):digest(p) for p in [evidence,inputs,predictions,model_path,boundaries,geocodes]},
        'historical_artifact_replay':'passed; probabilities and fixed threshold match saved predictions',
        'boundaries_source':SOURCE_URL, 'boundary_join':'DOSM polygons; ambiguous and uncertainty-overlapping district boundaries withheld',
        'privacy':'Only aggregate results are served. Exact points and service keys stay server-side.'}
    for name in sorted({r['district'] for r in rows}):
        subset = [r for r in rows if r['district']==name]
        summary['districts'].append({'district':name, **metrics(subset)})
    out.mkdir(parents=True,exist_ok=True)
    (out/'area_evaluation.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8')
    (out/'area_rows_private.json').write_text(json.dumps(rows,allow_nan=False),encoding='utf-8')
    shown={r['district'] for r in rows if r['district']!='Unassigned'}
    public_boundaries={'type':'FeatureCollection','features':[f for f in features
        if f['properties']['state']+' / '+f['properties']['district'] in shown]}
    (out/'district_boundaries_public.json').write_text(json.dumps(public_boundaries),encoding='utf-8')
    return summary

def radius_result(rows, lat, lon, km):
    if not all(math.isfinite(v) for v in (lat,lon,km)) or not (.5 <= lat <= 7.6 and 99 <= lon <= 120 and 1 <= km <= 50):
        raise ValueError('Choose a Malaysian location and a radius from 1 to 50 km')
    selected=[]; ambiguous=0
    for r in rows:
        if r['latitude'] is None: continue
        distance=haversine(lat,lon,r['latitude'],r['longitude'])
        if abs(distance-km) <= r['uncertainty_km'] + .1: ambiguous += 1
        elif distance < km: selected.append(r)
    if len(selected)<5: return {'services':len(selected),'status':'insufficient_services','ambiguous_boundary_services':ambiguous,
        'note':'At least five evaluated services required to show area outcome metrics.'}
    return {**metrics(selected),'ambiguous_boundary_services':ambiguous,'radius_km':km}
