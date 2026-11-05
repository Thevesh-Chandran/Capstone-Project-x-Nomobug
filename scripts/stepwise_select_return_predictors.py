"""Bidirectional stepwise selection; shares only earlier selection fits with forward search."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import pandas as pd
from threadpoolctl import threadpool_limits
from scripts import forward_select_return_predictors as f
from scripts import research_callback_targets as r

OUT=f.b.ROOT/'outputs/model_validation/20261017_stepwise_selection'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():raise ValueError('Preserve declared experiment')
    parent=json.loads((f.OUT/'protocol.json').read_text())
    assert r.digest(f.SOURCE)==parent['source_sha256']
    data=pd.read_pickle(f.SOURCE);parts,audits=f.partitions(data,parent['selection_folds'])
    frozen=f.b.ROOT/'outputs/cp2-v2/prospective_callback_v2'
    before={p.name:r.digest(p) for p in frozen.iterdir() if p.is_file()}
    protocol={**parent,'declared_at_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':r.digest(__file__),
      'shared_evaluator_sha256':r.digest(f.__file__),'parent_protocol_sha256':r.digest(f.OUT/'protocol.json'),
      'method':'Bidirectional stepwise: consider every one-variable addition and every one-variable removal each round',
      'rules':[
        'Start with best single variable, then consider additions and removals together.',
        'Accept only mean earlier F1 improvement >=0.005, with neither earlier fold losing >0.02 F1.',
        'Choose highest earlier mean F1; ties lower mean Brier, then operation and field name.',
        'Stop with no acceptable change, 20 selected variables, or 30 accepted moves.',
        'Never revisit an already accepted feature set; input reordering cannot create a selection cycle.',
        'Reuse exact ordered feature-list fits from forward search only on the two earlier selection periods.',
        'Do not read forward later assessment while selecting; lock the selected set before this later assessment.',
        'Same thresholds, purged chronological partitions, source and frozen safeguards as forward selection.',
        'Exploratory historical comparison, not fresh independent accuracy and no deployment.']}
    r.write(OUT/'protocol.json',protocol)
    cache={}
    # This file contains earlier selection fits only; never import later scores.
    if (f.OUT/'candidate_steps.jsonl').exists():
        for line in (f.OUT/'candidate_steps.jsonl').read_text().splitlines():
            item=json.loads(line);cache[tuple(item['columns'])]={k:item[k] for k in ['mean_f1','mean_ap','mean_brier','folds']}
    fits_new=0
    def evaluate(columns):
        nonlocal fits_new
        key=tuple(columns)
        if key not in cache:
            cache[key]=f.evaluate(columns,parts);fits_new+=len(parts)
        return cache[key]
    candidates=parent['eligible_candidates'];selected=[];path=[];visited={frozenset()}
    with threadpool_limits(limits=1):
        baseline=evaluate([]);current=baseline
        with ThreadPoolExecutor(max_workers=2) as executor:
            for move in range(1,31):
                proposals=[('add',x,selected+[x]) for x in candidates if x not in selected]
                if len(selected)>1:proposals += [('remove',x,[n for n in selected if n!=x]) for x in selected]
                proposals=[x for x in proposals if frozenset(x[2]) not in visited]
                def score(proposal):
                    operation,field,columns=proposal
                    return {'operation':operation,'field':field,'columns':columns,**evaluate(columns)}
                scored=list(executor.map(score,proposals))
                with (OUT/'candidate_moves.jsonl').open('a') as out:
                    for item in scored:out.write(json.dumps({'move':move,**item})+'\n')
                allowed=scored if not selected else [x for x in scored if f.acceptable(current,x)]
                if not allowed:reason='No addition or removal met the declared improvement rule';break
                best=sorted(allowed,key=lambda x:(-x['mean_f1'],x['mean_brier'],x['operation'],x['field']))[0]
                selected=best['columns'];current=best
                visited.add(frozenset(selected))
                path.append({'move':move,**best})
                r.write(OUT/'accepted_path.json',path)
                print(f'Move {move}: {best["operation"]} {best["field"]}; F1={best["mean_f1"]:.4f}',flush=True)
                if len(selected)>=20:reason='Declared 20-variable cap reached';break
            else:reason='Declared 30-move cap reached'
        r.write(OUT/'selection_locked.json',{'locked_at_utc':datetime.now(timezone.utc).isoformat(),'selected':selected,'path':path,'reason':reason})
        later,later_audits=f.partitions(data,parent['later_assessment_folds'])
        assessment={name:f.evaluate(cols,later) for name,cols in [('constant_baseline',[]),('selected',selected),('all_inputs',candidates)]}
    assert before=={p.name:r.digest(p) for p in frozen.iterdir() if p.is_file()}
    r.write(OUT/'results.json',{'selected':selected,'path':path,'selection_baseline':baseline,'stop_reason':reason,
      'new_selection_fits':fits_new,'later_assessment':assessment,'later_split_audits':later_audits,
      'frozen_bundle_unchanged':True,'status':'adaptive_historical_development'})
    print('Completed stepwise selection and later assessment',flush=True)

if __name__=='__main__':main()
