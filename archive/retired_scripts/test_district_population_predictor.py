"""Paired earlier-period test of a downloaded DOSM predictor; no test tuning."""
import json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from scripts.research_expanded_targets import OUT,DEV,save,sha,weather_data,scores
from scripts.research_customer_history_targets import dataset,features,partitions,fitted_model,DEST

def main():
    destination=OUT/'population_test';destination.mkdir(exist_ok=True)
    save(destination/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(OUT/'population_district.parquet'),
        'question':'Does 2020 district population improve 90/180-day repurchase prediction beyond purchase history and district category?',
        'new_inputs':['log district population in people','district population unknown flag'],
        'selection':'Use earlier-selected model/features/history and fixed threshold. Compare AP and Brier in each original development fold; retain only if both improve in every usable fold.',
        'limit':'Current revised census, coarse district context; not individual wealth, demand, building age or historical as-of publication archive. No assessment scoring here.'})
    pop=pd.read_csv(OUT/'district_population_2020.csv');mapping=dict(zip(pop.state+' / '+pop.district,pop.population*1000))
    customers=json.loads((OUT/'customers_private.json').read_text());w=weather_data();results=[];coverage=[]
    chosen=json.loads((DEST/'results.json').read_text())
    with threadpool_limits(limits=2):
        for horizon in [90,180]:
            d=dataset(customers,horizon,w);d['log_population']=np.log1p(d.district.map(mapping));d['population_unknown']=d.log_population.isna().astype(int)
            coverage.append({'horizon':horizon,'rows':len(d),'population_matched':int(d.log_population.notna().sum())})
            c=next(r for r in chosen if r['horizon']==horizon and r['policy']=='precision')['selected'];base=features(c['inputs'])
            for start,end in DEV:
                tr,va=partitions(d,start,end,c['window'])
                if len(tr)<50 or tr.label.nunique()<2 or va.label.nunique()<2:continue
                for group,cols in [('existing',base),('plus_population',base+['log_population','population_unknown'])]:
                    m=fitted_model(c['model'],cols);m.fit(tr[cols],tr.label);p=m.predict_proba(va[cols])[:,1]
                    results.append({'horizon':horizon,'period':start,'group':group,**scores(va.label,p,c['threshold'])})
    df=pd.DataFrame(results);df.to_csv(destination/'fold_metrics.csv',index=False);decisions=[]
    for h in [90,180]:
        a=df[(df.horizon==h)&df.group.eq('existing')].set_index('period');b=df[(df.horizon==h)&df.group.eq('plus_population')].set_index('period')
        good=(b.average_precision>a.average_precision)&(b.brier<a.brier)
        decisions.append({'horizon':h,'folds':len(good),'folds_both_improved':int(good.sum()),'retain':bool(good.all()),
            'mean_ap_existing':float(a.average_precision.mean()),'mean_ap_population':float(b.average_precision.mean()),
            'mean_brier_existing':float(a.brier.mean()),'mean_brier_population':float(b.brier.mean())})
    save(destination/'results.json',{'coverage':coverage,'decisions':decisions,'assessment_untouched':True});print(json.dumps(decisions))

if __name__=='__main__':main()
