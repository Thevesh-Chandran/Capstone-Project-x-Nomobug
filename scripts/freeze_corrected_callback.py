"""Refit fixed development selections on every corrected mature service.

Later holdout results are never used to choose features, models or thresholds.
Existing v1 bundles stay intact; this creates a separate corrected v2 bundle.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import joblib
try:
    from scripts import benchmark_warranty_models as b
    from scripts import compare_callback_candidates_v2 as c
    from scripts import freeze_callback_prospective as p
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    import compare_callback_candidates_v2 as c
    import freeze_callback_prospective as p


def freeze(input_path,selection_dir,output):
    if output.exists():raise ValueError('Corrected frozen bundle already exists')
    selection_path=selection_dir/'candidate_results.json'
    receipt=json.loads(selection_path.read_text(encoding='utf-8'))
    if receipt['feature_preparation_source_sha256']['comparison']!=p.digest(Path(c.__file__)):
        raise ValueError('Candidate preparation changed after selection')
    frame=c.prepare_input(b.load_dataset_input(input_path));now=datetime.now(timezone.utc)
    today=now.astimezone(p.LOCAL).date();c.ensure_mature(frame,today)
    output.mkdir(parents=True)
    manifest={'version':'prospective_callback_v2_corrected','preparation':'candidate_v5',
        'status':'frozen_not_operational_no_future_performance','frozen_at_utc':now.isoformat(),
        'cohort_start':str(today+timedelta(days=1)),'cohort_end':str(today+timedelta(days=30)),
        'earliest_final_evaluation_date':str(today+timedelta(days=61)),
        'target':'recorded_corrective_calendar_callback_within_30d','date_authority':'Calendar','review_fraction':.2,
        'input_file_sha256':p.digest(input_path),'training_input_relative_path':str(input_path.resolve().relative_to(b.ROOT)),
        'training_rows':len(frame),'training_positive_rows':int(frame[b.TARGET].sum()),
        'training_2026_rows':int(frame.anchor_date.ge('2026-01-01').sum()),
        'latest_training_anchor':str(frame.anchor_date.max().date()),
        'latest_training_outcome_end':str(frame.outcome_end_date.max().date()),
        'development_selection_sha256':p.digest(selection_path),'training_replay_file':'training_replay_private.csv',
        'feature_preparation_hashes':{str(path.relative_to(b.ROOT)):p.digest(path) for path in
            [b.ROOT/'scripts/benchmark_warranty_models.py',b.ROOT/'scripts/compare_callback_blind_spots.py',
             b.ROOT/'scripts/compare_callback_candidates_v2.py']},
        'upstream_contract_hashes':{str(path.relative_to(b.ROOT)):p.digest(path) for path in
            [b.ROOT/'dbt/macros/calendar_history_available.sql',b.ROOT/'dbt/macros/calendar_snapshot_observation_sql.sql',
             b.ROOT/'dbt/macros/warranty_anchor_dataset_sql.sql']},'models':{},
        'limits':['Training includes the later retrospective holdout only after its evaluation; no future accuracy is measured.',
            'Calibrators and thresholds stay from the fixed purged development predictions.',
            'Live predictor extraction and full prospective outcome capture remain required.',
            'Predictors must exclude future-created history and use complete-day coverage.',
            'Timestamp declarations do not independently establish every upstream feature availability.']}
    replay=frame[p.KEYS].copy();replay.anchor_date=replay.anchor_date.dt.strftime('%Y-%m-%d')
    cache={}
    for role,name in [('reference','reference_all_history'),('selected_ap','challenger_all_history'),('selected_priority','priority_all_history')]:
        source=selection_dir/role/'all_mature_model.joblib'
        if p.digest(source)!=receipt['results'][role]['all_mature_model_sha256']:
            raise ValueError('Development artifact changed')
        artifact=joblib.load(source);members=[]
        for member,weight in artifact['selection']['members']:
            if member not in cache:cache[member]=c.fit_member(member,frame,artifact['numeric_feature_sets'])
            members.append(cache[member]|{'weight':weight})
        features=sorted({f for member in members for f in member['features']})
        artifact={**artifact,'members':members,'features':features,'frozen_at_utc':now.isoformat(),
            'purpose':'corrected_all_mature_prospective_refit_not_deployment','training_rows':len(frame),
            'training_positive_rows':int(frame[b.TARGET].sum()),'input_file_sha256':p.digest(input_path),
            'training_max_anchor_date':str(frame.anchor_date.max().date()),
            'training_max_outcome_end_date':str(frame.outcome_end_date.max().date()),'created_at':now.isoformat()}
        path=output/(name+'.joblib');joblib.dump(artifact,path)
        replay[name]=p.artifact_probability(artifact,frame)
        manifest['models'][name]={'file':path.name,'sha256':p.digest(path),'features':features,
            'selection_name':artifact['selection']['name'],'threshold':artifact['threshold'],
            'source_development_artifact_sha256':p.digest(source)}
    replay.to_csv(output/manifest['training_replay_file'],index=False)
    manifest['training_replay_sha256']=p.digest(output/manifest['training_replay_file'])
    (output/'bundle.json').write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding='utf-8')
    return {'training_rows':len(frame),'positive_rows':int(frame[b.TARGET].sum()),'models':list(manifest['models']),
        'future_performance':'not_measured','bundle':str(output/'bundle.json')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-json',type=Path,required=True);parser.add_argument('--selection-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(freeze(args.input_json,args.selection_dir,args.output_dir),indent=2))


if __name__=='__main__':main()
