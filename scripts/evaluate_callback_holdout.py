"""One-time later-date comparison of models frozen before reading holdout labels."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import joblib
import numpy as np
try:
    from scripts import benchmark_warranty_models as b
    from scripts.compare_callback_candidates_v2 import prepare_input,predict_artifact
    from scripts.compare_callback_blind_spots import segment_metrics
    from scripts.callback_evaluation import paired_intervals
except ModuleNotFoundError:
    import benchmark_warranty_models as b
    from compare_callback_candidates_v2 import prepare_input,predict_artifact
    from compare_callback_blind_spots import segment_metrics
    from callback_evaluation import paired_intervals
KEYS=['population','sales_record_id','anchor_date']


def evaluate(input_path,model_dir,output):
    if output.exists():raise ValueError('Later holdout evaluation already exists; do not retune/retest it')
    selection_path=model_dir/'candidate_results.json'
    selections=json.loads(selection_path.read_text(encoding='utf-8'))
    frame=prepare_input(b.load_dataset_input(input_path))
    if frame.empty:raise ValueError('Nonempty holdout required')
    first=frame.anchor_date.min()
    if not (frame.anchor_date>np.datetime64('2026-08-14')).all():raise ValueError('Holdout contains development-era anchors')
    results={};predictions={};hashes={}
    for role in ['reference','selected_ap','selected_priority']:
        path=model_dir/role/'historical_model.joblib';artifact=joblib.load(path)
        expected=selections['results'][role]['historical_fit']['artifact_sha256']
        hashes[role]=hashlib.sha256(path.read_bytes()).hexdigest()
        if hashes[role]!=expected:raise ValueError('Model changed after development selection')
        if np.datetime64(artifact['training_max_outcome_end_date'])>=first.to_datetime64():
            raise ValueError('Training outcomes were not complete before held-out services')
        scored=predict_artifact(artifact,frame).merge(frame[KEYS+[b.TARGET]],on=KEYS,validate='one_to_one')
        probabilities=scored.probability.to_numpy();predictions[role]=scored
        results[role]={'selection':artifact['selection']['name'],
            'training_rows':artifact['training_rows'],'training_positive_rows':artifact['training_positive_rows'],
            'training_max_outcome_end_date':artifact['training_max_outcome_end_date'],
            'metrics':b.score(scored[b.TARGET],probabilities,artifact['threshold']),
            'priority_top20pct':b.priority_review_metrics(scored[b.TARGET],probabilities),
            'segments':segment_metrics(frame,probabilities,artifact['threshold'])}
    report={'evaluated_at_utc':datetime.now(timezone.utc).isoformat(),'status':'retrospective_future_services_not_online_prediction',
        'input_file_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),
        'development_selections_sha256':hashlib.sha256(selection_path.read_bytes()).hexdigest(),
        'models_sha256':hashes,'rows':len(frame),'positive_rows':int(frame[b.TARGET].sum()),
        'start':str(first.date()),'end':str(frame.anchor_date.max().date()),
        'results':results,'paired_intervals':{role:paired_intervals(frame,predictions['reference'],predictions[role])
            for role in ['selected_ap','selected_priority']},
        'limitations':['Models selected before reading this holdout; no subsequent tuning on its results.',
            'Returning customers can appear in prior training; this measures future operational services.',
            'Historical feature revisions cannot all be reconstructed; creation-time gates remove provable future history.',
            'Small callback counts limit confidence; this is distinct from the prospective live cohort.']}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    for role,prediction in predictions.items():prediction.to_csv(output.parent/f'{role}_predictions_private.csv',index=False)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-json',type=Path,required=True)
    p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--output-json',type=Path,required=True)
    args=p.parse_args();print(json.dumps(evaluate(args.input_json,args.model_dir,args.output_json),indent=2,allow_nan=False))


if __name__=='__main__':main()
