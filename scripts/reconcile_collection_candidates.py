"""Read-only review of missed windows against a declared current source snapshot.

This does not edit collector state, model receipts or eligibility at prediction
time. Current reconstructed eligibility is kept separate from historical audit.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from scripts import cp2_pipeline as pipeline, cp2_pipeline_tick as tick
from scripts.benchmark_warranty_models import load_dataset_input


def reconcile(history, calendar, old_calendar, candidates, predictors, start, end):
    old_ids={(r['calendar_id'],r['event_id']):r['calendar_event_row'] for r in old_calendar['records']}
    by_key={}; row_keys={}
    for event in calendar['records']:
        identity=(event['calendar_id'],event['event_id'])
        stable=old_ids.get(identity,-int(hashlib.sha256(json.dumps(identity,separators=(',',':')).encode()).hexdigest()[:15],16)-1)
        key=tick.event_key(event)
        if key in by_key or stable in row_keys:raise ValueError('Duplicate Calendar identity')
        by_key[key]=event;row_keys[stable]=key
    diagnostic={row_keys[int(r['calendar_event_row'])]:r for r in candidates}
    eligible={row_keys[int(r['anchor_event_row'])] for r in predictors}
    reviews=[]
    for key,missed_at in history.get('missed',{}).items():
        day=history.get('missed_anchor_dates',{}).get(key,'')
        if not start<=day<=end:continue
        event=by_key.get(key);candidate=diagnostic.get(key)
        if event is None:reason='current_calendar_key_missing'
        elif tick.service_window(event) is None:reason='current_cancelled_or_nonservice'
        elif key in eligible:reason='currently_eligible_anchor'
        elif candidate is None:reason='absent_from_current_candidate_population'
        elif candidate['population_reason']=='candidate':reason='not_in_frozen_predictor_population'
        else:reason=candidate['population_reason']
        reviews.append({'event_key':key,'anchor_date':day,'original_missed_at':missed_at,
            'original_decision':history.get('event_decisions',{}).get(key,'not_yet_classified'),
            'current_reconstruction':reason,
            'current_title':event.get('summary') if event else None,
            'current_start':event.get('start_raw') if event else None,
            'matched_sales_record_id':candidate.get('matched_sales_record_id') if candidate else None})
    return {'observed_at_utc':datetime.now(timezone.utc).isoformat(),'cohort_start':start,'cohort_end':end,
        'candidate_windows':len(reviews),'original_decisions':dict(Counter(r['original_decision'] for r in reviews)),
        'current_reconstruction_counts':dict(Counter(r['current_reconstruction'] for r in reviews)),
        'interpretation':'Current reconstruction is not evidence of eligibility or source availability at prediction time. Original misses are preserved.',
        'reviews':reviews}


def main():
    p=argparse.ArgumentParser();p.add_argument('--review-dir',type=Path,required=True)
    p.add_argument('--source-dir',type=Path,required=True);args=p.parse_args()
    root=Path(__file__).resolve().parents[1];out=args.review_dir.resolve()
    args.source_dir=args.source_dir.resolve()
    if not out.is_relative_to(root/'outputs'):raise ValueError('Private review must stay in outputs')
    read=lambda path:json.loads(path.read_text(encoding='utf-8'))
    protocol=read(root/'config/cp2_october10_cohort.json')
    result=reconcile(read(out/'watch_events_before_private.json'),read(args.source_dir/'calendar_private.json'),
        read(root/'outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json'),
        read(out/'features/collection_candidates_private.json'),
        load_dataset_input(out/'features/predictors/dataset_input.json').to_dict('records'),
        protocol['cohort_start'],protocol['cohort_end'])
    result['provenance']={str(path.relative_to(root)):pipeline.digest(path) for path in
        [out/'watch_events_before_private.json',args.source_dir/'calendar_private.json',
         out/'features/collection_candidates_private.json',out/'features/predictors/dataset_input.json']}
    (out/'candidate_review_private.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    summary={k:v for k,v in result.items() if k not in ('reviews','provenance')}
    (out/'candidate_review_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':main()
