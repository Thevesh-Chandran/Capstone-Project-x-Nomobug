"""Recreate development-only receipts after interrupted export; no test access."""
import itertools,json
import pandas as pd
from threadpoolctl import threadpool_limits
from scripts.research_expanded_targets import OUT,FAMILIES,GROUPS,WINDOWS,DEV,repeat_data,weather_data,split_repeat,columns,classifier,scores,save

def main():
    w=weather_data();customers=json.loads((OUT/'customers_private.json').read_text());rows=[];audits=[]
    with threadpool_limits(limits=2):
        for h in [30,60,90,180]:
            d,excluded=repeat_data(customers,h,w);audits.append({'horizon':h,'eligible':len(d),'excluded':excluded})
            board=[]
            for model,group,window in itertools.product(FAMILIES,GROUPS,WINDOWS):
                ys=[];ps=[];cols=columns(group)
                for start,end in DEV:
                    tr,va=split_repeat(d,start,end,window)
                    if len(tr)<50 or tr.label.nunique()<2 or va.label.nunique()<2:continue
                    m=classifier(model,cols);m.fit(tr[cols],tr.label);ys.extend(va.label);ps.extend(m.predict_proba(va[cols])[:,1])
                for t in [.05,.1,.15,.2,.3,.4,.5,.6,.7,.8]:board.append({'target':f'repeat_{h}','model':model,'inputs':group,'history':window,'threshold':t,**scores(ys,ps,t)})
            eligible=[r for r in board if r['recall']>=.3 and r['predicted_positive']>=10];chosen=max(eligible or board,key=lambda r:(r['f1'],r['precision']))
            original=json.loads((OUT/f'repeat_{h}_selection.json').read_text())['selected_before_assessment']
            assert all(chosen[k]==original[k] for k in ['model','inputs','history','threshold','tp','fp','fn','tn'])
            rows.extend(board);print('Development receipts reproduced',h,flush=True)
    pd.DataFrame(rows).to_csv(OUT/'repeat_development_search.csv',index=False);save(OUT/'repeat_data_audit.json',audits)
    save(OUT/'development_recovery.json',{'all_original_selections_reproduced':True,'assessment_not_read_or_changed':True,'rows':len(rows)})

if __name__=='__main__':main()
