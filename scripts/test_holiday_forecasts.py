"""Validate holiday inputs on prior forecast development origins only."""
import json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from scripts.research_expanded_targets import OUT as OLD,weather_data,weekly_matrix,forecaster,regression_metrics,save
from scripts.test_age_holiday_predictors import OUT,DATES

def weekly_festivals(date):
    events=pd.DatetimeIndex([pd.Timestamp(f'{y}-{day}') for y,days in DATES.items() for day in days])
    delta=(events-pd.Timestamp(date)).days.to_numpy()
    return {'festival_days_next_week':int(((delta>=0)&(delta<7)).sum()),'festival_days_previous_week':int(((delta>=-7)&(delta<0)).sum()),
        'festival_days_week_after_next':int(((delta>=7)&(delta<14)).sum())}

def main():
    assert not (OUT/'forecast_holiday_protocol.json').exists()
    save(OUT/'forecast_holiday_protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),
        'selection':'Use previous selected model/history/weather settings. Paired earlier development origins Jan-June2026 every second week. Require MAE >=10% lower to merit a later follow-up. No later assessment reused here.',
        'inputs':'Number of nominal common regional festival dates in previous week, forecast week, week after. These dates were on the2026 calendar published in2025. Calendar may omit substitution and one-off holidays.'})
    series=pd.read_csv(OLD/'weekly_targets.csv',index_col=0,parse_dates=True);w=weather_data();chosen=json.loads((OLD/'forecast_results.json').read_text());rows=[];results=[]
    with threadpool_limits(limits=2):
        for r in chosen:
            target=r['target'];c=r['selected'];d=weekly_matrix(series[target].dropna(),w)
            extra=pd.DataFrame([weekly_festivals(v) for v in d.date],index=d.index);d=d.join(extra)
            base=[col for col in d if col not in ['date','actual',*extra.columns] and (c['inputs']=='weather' or col not in ['rain_7','rain_28','temperature_28','humidity_28'])]
            dev=d[d.date.between('2026-01-05','2026-06-29')].iloc[::2]
            for name,cols in [('Existing',base),('Add festival weeks',base+list(extra.columns))]:
                pp=[]
                for _,row in dev.iterrows():
                    tr=d[d.date<row.date]
                    if c['history']=='52_weeks':tr=tr[tr.date>=row.date-pd.Timedelta(weeks=52)]
                    m=forecaster(c['model']);m.fit(tr[cols],tr.actual);p=max(0,float(m.predict(pd.DataFrame([row[cols]]))[0]));pp.append(p)
                    rows.append({'target':target,'variant':name,'date':str(row.date.date()),'actual':row.actual,'prediction':p})
                results.append({'target':target,'variant':name,**regression_metrics(dev.actual,pp)})
    pd.DataFrame(rows).to_csv(OUT/'forecast_holiday_development_predictions.csv',index=False)
    df=pd.DataFrame(results);df.to_csv(OUT/'forecast_holiday_comparison.csv',index=False);decisions=[]
    for target,part in df.groupby('target',sort=False):
        a=part[part.variant.eq('Existing')].iloc[0];b=part[part.variant.eq('Add festival weeks')].iloc[0];improvement=1-b.mae/a.mae
        decisions.append({'target':target,'development_mae_change_percent':float(improvement*100),'candidate':bool(improvement>=.1)})
    save(OUT/'forecast_holiday_decisions.json',{'decisions':decisions,'later_assessment_not_used':True});print(json.dumps(decisions))

if __name__=='__main__':main()
