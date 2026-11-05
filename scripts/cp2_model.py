"""Single entry point for the current CP2 callback model and validation bundle."""
from __future__ import annotations
import argparse,json
from pathlib import Path
try:
    from scripts import freeze_callback_prospective as p
except ModuleNotFoundError:
    import freeze_callback_prospective as p


def current_bundle():
    registry=json.loads((p.b.ROOT/'config/cp2_model_current.json').read_text(encoding='utf-8'))
    bundle=p.b.ROOT/registry['bundle_relative_path']
    if p.digest(bundle/'bundle.json')!=registry['bundle_sha256']:
        raise ValueError('Current model bundle changed; review registry before use')
    return registry,bundle


def readiness(registry):
    """Report evidence limits; successful collection never implies approval."""
    evidence=registry.get('new_retrospective_test',{})
    accuracy=evidence.get('threshold_accuracy')
    baseline=evidence.get('always_no_callback_accuracy')
    def probability(value):
        return isinstance(value,(int,float)) and not isinstance(value,bool) and 0 <= value <= 1
    comparable=probability(accuracy) and probability(baseline)
    return {
        'model_version':registry.get('version'),
        'operational_approved':False,
        'permitted_use':'experimental risk scoring and documented research evaluation',
        'historical_accuracy_beats_baseline':accuracy > baseline if comparable else None,
        'historical_accuracy':accuracy if probability(accuracy) else None,
        'historical_no_callback_baseline':baseline if probability(baseline) else None,
        'historical_services':evidence.get('services'),
        'historical_positive_windows':evidence.get('callback_positive_service_windows'),
        'replacement_qualified':registry.get('research_review',{}).get('replacement_qualified') is True,
        'earliest_full_outcome_evaluation':registry.get('october10_earliest_final_evaluation',registry.get('earliest_final_evaluation')),
        'limits':[
            'This report does not authorize operational use, even if a historical accuracy improves.',
            evidence.get('limits','Historical performance evidence is missing.'),
            'The declared cohorts require complete timely predictions and mature Calendar outcomes; missing predictions cannot be backfilled.',
            'A working cloud collector is evidence of collection, not evidence of model reliability.',
        ],
    }


def predict(bundle,input_path,output):
    output=output.resolve()
    if not output.is_relative_to((p.b.ROOT/'outputs').resolve()):
        raise ValueError('Customer-level predictions must stay in ignored project outputs')
    if output.exists():raise ValueError('Prediction output already exists')
    p.configure_contracts(False);manifest,models=p.load_bundle(bundle)
    frame=p.prepare_scoring_frame(p.b.load_dataset_input(input_path),manifest.get('preparation'))
    result=frame[p.KEYS].copy()
    for name,artifact in models.items():result[name]=p.artifact_probability(artifact,frame)
    result['prediction_status']='risk_score_only_not_observed_outcome'
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='') as handle:result.to_csv(handle,index=False)
    return {'scored_services':len(result),'output':str(output),
        'note':'This command does not register prospective predictions or measure accuracy.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['status','readiness','verify','predict','log-prospective','prepare-prospective-labels','evaluate-prospective'])
    parser.add_argument('--input-json',type=Path);parser.add_argument('--output-csv',type=Path)
    parser.add_argument('--source-receipt',type=Path);parser.add_argument('--output-json',type=Path)
    args=parser.parse_args();registry,bundle=current_bundle()
    if args.mode=='status':result=registry
    elif args.mode=='readiness':result=readiness(registry)
    elif args.mode=='verify':result=p.verify(bundle)
    elif args.mode=='predict':
        if not args.input_json or not args.output_csv:parser.error('predict requires --input-json and --output-csv')
        result=predict(bundle,args.input_json,args.output_csv)
    else:
        if not args.input_json:parser.error('input JSON required')
        logs=p.b.ROOT/'outputs/cp2-v2/live_pipeline/prospective_logs'
        if args.mode in ['log-prospective','prepare-prospective-labels']:
            if not args.source_receipt:parser.error('source receipt JSON required')
            receipt=json.loads(args.source_receipt.read_text(encoding='utf-8'))
            if args.mode=='log-prospective':result=p.score(bundle,args.input_json,logs,source_receipt=receipt)
            else:
                if not args.output_json:parser.error('prepare-prospective-labels requires --output-json')
                result=p.prepare_labels(bundle,args.input_json,receipt,args.output_json)
        else:result=p.evaluate(bundle,args.input_json,logs)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
