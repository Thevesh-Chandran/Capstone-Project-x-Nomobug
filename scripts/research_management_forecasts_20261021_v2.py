"""Bounded retrospective booking-flow research, with timestamp availability gates.

An observed current record last updated before an origin can be used; the file
does NOT recreate old versions, deleted events or the true historical live view.
No source, frozen model, collector, production table or operational site writes.
"""
from __future__ import annotations

import os
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
from pathlib import Path
from datetime import datetime, timezone
from itertools import product
import hashlib
import html
import json
import math
import re
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/model_validation/20261021_management_forecasts_v2'
SOURCE = ROOT/'outputs/reporting_release/20261014042133f459ce/calendar_private.json'
WEATHER_SOURCE = ROOT/'outputs/model_validation/20261018_expanded_targets/regional_weather.json'
HOLIDAY_SOURCE = ROOT/'outputs/model_validation/20261018_age_holidays/festival_dates_transcribed.json'
SEED = 20261021
START = pd.Timestamp('2024-05-06')
END = pd.Timestamp('2026-10-12')
DEV = pd.date_range('2026-01-05', '2026-06-29', freq='2W-MON')
ASSESS = pd.date_range('2026-07-06', '2026-10-05', freq='W-MON')
TARGETS = ['booking_entries', 'booked_hours']
HORIZONS = [1, 2]
FAMILIES = ['ridge_1', 'ridge_100', 'random_forest', 'extra_trees', 'boosting']
HISTORY = [52, 78, 1000]
GROUPS = ['activity_calendar', 'activity_calendar_weather']
BASELINES = ['visible_only', 'mean4_total', 'mean8_total', 'mean13_total', 'mean8_late_additions', 'median8_late_additions']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')


def now():
    return datetime.now(timezone.utc).isoformat()


def events():
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    raw = pd.DataFrame(source['records'])
    assert not raw.duplicated(['calendar_id', 'event_id']).any()
    title = raw.summary.fillna('').str.upper()
    cancelled = raw.status.eq('cancelled') | title.str.contains(r'^\s*CANCEL(?:L)?ED\b', regex=True)
    admin = title.str.contains(r'\b(?:CHECK|REVIEW|CALCULATE)\b.*\bCONVERSION\s+RATE\b', regex=True)
    explicit = title.str.replace(r'\b(?:NO|WITHOUT)\s+WARRANTY\b', '', regex=True).str.contains(r'\b(?:WARRANTY|CLAIMS?|CALLBACK)\b', regex=True)
    seq = title.str.extract(r'\b(\d{1,2})\s*/\s*(\d{1,2})\b').apply(pd.to_numeric, errors='coerce')
    over = seq[0] > seq[1]
    consultation = title.str.contains(r'\b(?:CONSULTATION|INSPECTION)\b', regex=True)
    complimentary = title.str.contains(r'\b(?:EXTRA|COMPLIMENTARY|FOLLOW[- ]?UP)\b', regex=True)
    selected = raw.status.eq('confirmed') & ~cancelled & ~admin & (explicit | (~consultation & (over | complimentary | seq[0].notna())))
    data = raw.loc[selected].copy()
    for src, dst in [('start_raw', 'start'), ('end_raw', 'end'), ('created_raw', 'created'), ('updated_raw', 'updated')]:
        data[dst] = pd.to_datetime(data[src], utc=True, format='mixed', errors='coerce').dt.tz_convert('Asia/Kuala_Lumpur').dt.tz_localize(None)
    data = data[data.start.ge('2023-10-09') & data.start.lt(END)].copy()
    data['hours'] = (data.end-data.start).dt.total_seconds()/3600
    data['week'] = data.start.dt.to_period('W-SUN').dt.start_time
    assert data[['start','end','created','updated']].notna().all().all()
    assert data.hours.between(.25, 12).all()
    assert not data.is_all_day.any()
    data['available'] = data[['created','updated']].max(axis=1)
    data['unit'] = 1.0
    audit = {
        'raw_snapshot_rows':len(raw), 'eligible_recorded_booking_entries':len(data),
        'snapshot_metadata':source['metadata'],
        'first_booked_date':str(data.start.min()), 'last_booked_date':str(data.start.max()),
        'booked_hours':float(data.hours.sum()), 'longer_than_8h_entries':int(data.hours.gt(8).sum()),
        'latest_update_after_booked_start':int((data.updated>data.start).sum()),
        'latest_update_more_than_7d_after_start':int((data.updated>data.start+pd.Timedelta(days=7)).sum()),
        'selection':'dbt calendar_event_category title/status rules reproduced; service/warranty/complimentary. Consultation/admin/cancelled excluded. Exact owner temporary-slot review overrides are not reconstructed here.',
        'grain':'One calendar_id plus event_id entry; cross-calendar duplicates may still represent the same visit. Not a completed treatment.',
        'limitation':'Current surviving versions only. Availability gate excludes later-edited records instead of reconstructing their old state. Deleted/moved appointments cannot be restored. All results retrospective and exploratory.',
    }
    return data, audit


def context():
    weather = pd.DataFrame(json.loads(WEATHER_SOURCE.read_text(encoding='utf-8'))['daily'])
    weather.index = pd.to_datetime(weather.pop('time'))
    holiday_json = json.loads(HOLIDAY_SOURCE.read_text(encoding='utf-8'))
    holidays = pd.DatetimeIndex([pd.Timestamp(f'{year}-{date}') for year, dates in holiday_json.items() for date in dates])
    return weather, holidays


def available_past(data, origin, length=13):
    known = data[data.available.lt(origin) & data.start.lt(origin)]
    index = pd.date_range(origin-pd.Timedelta(weeks=length), origin-pd.Timedelta(weeks=1), freq='W-MON')
    return known.groupby('week').agg(booking_entries=('unit','sum'),booked_hours=('hours','sum')).reindex(index,fill_value=0)


def matrix(data, target, horizon, weather, holidays):
    rows=[]
    for origin in pd.date_range(START,END-pd.Timedelta(weeks=horizon),freq='W-MON'):
        finish=origin+pd.Timedelta(weeks=horizon)
        future=data[data.start.ge(origin) & data.start.lt(finish)]
        visible=future[future.available.lt(origin)]
        value='unit' if target=='booking_entries' else 'hours'
        past=available_past(data,origin)
        actual=float(future[value].sum());stock=float(visible[value].sum())
        row={'origin':origin,'outcome_end':finish,'last_outcome_update':future.available.max() if len(future) else finish,
             'actual':actual,'visible':stock,'late_additions':actual-stock,
             'week_sin':math.sin(origin.isocalendar().week*2*math.pi/52.18),
             'week_cos':math.cos(origin.isocalendar().week*2*math.pi/52.18),
             'time_index_weeks':(origin-pd.Timestamp('2023-10-09')).days/7,
             'festival_days_next':int(((holidays>=origin)&(holidays<finish)).sum()),
             'festival_days_previous':int(((holidays>=origin-pd.Timedelta(days=7))&(holidays<origin)).sum())}
        for series in TARGETS:
            vals=past[series].to_numpy()
            for lag in [1,2,3,4,8,13]:row[f'{series}_lag{lag}']=float(vals[-lag])
            for window in [4,8,13]:
                row[f'{series}_mean{window}']=float(vals[-window:].mean())
                row[f'{series}_sd{window}']=float(vals[-window:].std())
            row[f'{series}_change4']=float(vals[-4:].mean()-vals[-8:-4].mean())
        # Only old weather; ERA5 reanalysis publication delay of at least 7 days.
        cutoff=origin-pd.Timedelta(days=7)
        w=weather[(weather.index>=cutoff-pd.Timedelta(days=28)) & (weather.index<cutoff)]
        assert len(w)==28 and w.index.max()<origin-pd.Timedelta(days=7)
        row['weather_rain7']=float(w.iloc[-7:].precipitation_sum.sum())
        row['weather_rain28']=float(w.precipitation_sum.sum())
        row['weather_temperature28']=float(w.temperature_2m_mean.mean())
        row['weather_humidity28']=float(w.relative_humidity_2m_mean.mean())
        # Visible stock is partial future information actually entered in advance;
        # it is a lawful predictor but never treated as the complete future target.
        assert 0<=stock<=actual+1e-9
        rows.append(row)
    result=pd.DataFrame(rows)
    assert result.origin.is_unique and result.actual.ge(0).all()
    return result


def feature_columns(d,group):
    excluded={'origin','outcome_end','last_outcome_update','actual','late_additions'}
    cols=[c for c in d if c not in excluded and (group.endswith('weather') or not c.startswith('weather_'))]
    assert not {'actual','late_additions','outcome_end','last_outcome_update'}&set(cols)
    return cols


def train_rows(d,origin,history):
    result=d[d.outcome_end.le(origin) & d.last_outcome_update.lt(origin) & d.origin.ge(origin-pd.Timedelta(weeks=history))]
    assert result.empty or ((result.outcome_end<=origin)&(result.last_outcome_update<origin)&(result.origin<origin)).all()
    return result


def estimator(name):
    if name.startswith('ridge_'):
        return make_pipeline(StandardScaler(),Ridge(alpha=float(name.split('_')[1])))
    if name=='random_forest':return RandomForestRegressor(n_estimators=40,max_depth=4,min_samples_leaf=5,n_jobs=2,random_state=SEED)
    if name=='extra_trees':return ExtraTreesRegressor(n_estimators=40,max_depth=4,min_samples_leaf=5,n_jobs=2,random_state=SEED)
    if name=='boosting':return HistGradientBoostingRegressor(max_iter=60,max_leaf_nodes=5,min_samples_leaf=6,l2_regularization=10,early_stopping=False,random_state=SEED)
    raise ValueError(name)


def forecast(d, row, config, horizon):
    name=config['family'];tr=train_rows(d,row.origin,config['history_weeks'])
    if len(tr)<8:raise ValueError(f'Insufficient matured earlier windows: {len(tr)} at {row.origin}')
    if name=='visible_only':prediction=row.visible
    elif name in ['mean4_total','mean8_total','mean13_total']:
        window=int(re.search(r'\d+',name).group());target=config['target']
        # Mean is based on timestamp-filtered past events, not final revised stock.
        prediction=row[f'{target}_mean{window}']*horizon
    elif name=='mean8_late_additions':prediction=row.visible+tr.tail(8).late_additions.mean()
    elif name=='median8_late_additions':prediction=row.visible+tr.tail(8).late_additions.median()
    else:
        cols=feature_columns(d,config['features']);m=estimator(name)
        scale=max(1,float(tr.late_additions.mean()))
        m.fit(tr[cols],tr.late_additions/scale)
        extra=max(0,float(m.predict(pd.DataFrame([row[cols]]))[0])*scale)
        prediction=row.visible+extra
    assert np.isfinite(prediction)
    return max(0,float(prediction)),len(tr)


def metrics(rows):
    d=pd.DataFrame(rows);error=d.prediction-d.actual
    return {'origins':len(d),'mae':float(error.abs().mean()),'rmse':float(np.sqrt(np.square(error).mean())),
            'wape':float(error.abs().sum()/d.actual.sum()),'bias':float(error.mean()),
            'mean_actual':float(d.actual.mean()),'actual_total_across_windows':float(d.actual.sum()),
            'mean_visible_share':float(np.mean(d.visible/np.maximum(1,d.actual))),
            'mean_train_windows':float(d.training_windows.mean())}


def evaluate(d,origins,config,horizon,phase):
    wanted=d[d.origin.isin(origins)];assert len(wanted)==len(origins)
    rows=[]
    for _,r in wanted.iterrows():
        p,n=forecast(d,r,config,horizon)
        rows.append({'origin':str(r.origin.date()),'actual':r.actual,'visible':r.visible,'prediction':p,'training_windows':n,
                     'target':config['target'],'horizon_weeks':horizon,'phase':phase,'configuration':config['id']})
    return rows


def bootstrap(selected,baseline,horizon):
    a=pd.DataFrame(selected);b=pd.DataFrame(baseline)
    assert a.origin.tolist()==b.origin.tolist()
    diff=(b.prediction-b.actual).abs().to_numpy()-(a.prediction-a.actual).abs().to_numpy()
    rng=np.random.default_rng(SEED);n=len(diff);block=max(2,horizon);boot=[]
    for _ in range(3000):
        idx=np.concatenate([(s+np.arange(block))%n for s in rng.integers(0,n,math.ceil(n/block))])[:n]
        boot.append(float(diff[idx].mean()))
    return {'baseline_minus_selected_mae_95pct_interval':np.quantile(boot,[.025,.975]).tolist(),
            'fraction_origins_selected_lower_error':float(np.mean(diff>0)),'block_length':block,
            'warning':'Exploratory dependent historical sample; no multiple-search-adjusted inference.'}


def html_report(results,audit):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[]
    for result in results:
        key=result['task'];pred=pd.read_csv(OUT/f'{key}_assessment.csv')
        fig,ax=plt.subplots(figsize=(9,3.2));x=pd.to_datetime(pred.origin)
        ax.plot(x,pred.actual,label='Recorded outcome',color='#101828',linewidth=2)
        ax.plot(x,pred.selected,label='Validation-selected forecast',color='#2667ff',marker='o',markersize=3)
        ax.plot(x,pred.baseline,label='Strong baseline',color='#f4a340',linestyle='--')
        ax.set_ylabel('Bookings' if result['target']=='booking_entries' else 'Booked hours')
        ax.set_title(f"Next {result['horizon_weeks']} week(s)");ax.legend(frameon=False,fontsize=8)
        ax.spines[['top','right']].set_visible(False);fig.autofmt_xdate();fig.tight_layout()
        fig.savefig(OUT/f'{key}.png',dpi=140);plt.close(fig)
        s=result['assessment'];b=result['baseline_assessment'];v=result['visible_only_assessment']
        rows.append({'Question':f"Next {result['horizon_weeks']} week(s): {result['target'].replace('_',' ')}",
                     'Selected':result['selected']['family'],'Forecast MAE':round(s['mae'],2),'Baseline MAE':round(b['mae'],2),
                     'Visible-only MAE':round(v['mae'],2),'WAPE':f"{s['wape']:.1%}",'Research gate':result['research_gate_passed']})
    table=pd.DataFrame(rows).to_html(index=False,border=0)
    figures=''.join(f'<section><h2>{html.escape(r["task"].replace("_"," "))}</h2><img src="{r["task"]}.png" alt="Historical forecast comparison"></section>' for r in results)
    content=f'''<!doctype html><html><head><meta charset="utf-8"><title>Nomobug booking forecasts</title><style>
    body{{font:16px/1.65 system-ui,sans-serif;color:#152238;background:#f3f6fb;margin:0}}main{{max-width:1120px;margin:auto;padding:40px}}h1{{font-size:36px;line-height:1.2}}h2{{font-size:23px}}.tag{{color:#175cd3}}section,.card{{background:white;padding:25px 30px;border:1px solid #dfe5ee;border-radius:14px;margin:20px 0}}table{{border-collapse:collapse;font-size:14px;width:100%}}td,th{{padding:11px;text-align:left;border-bottom:1px solid #e5e9ef}}th{{background:#edf3ff}}img{{width:100%;max-width:1000px}}.warning{{border-left:4px solid #e9a23b}}code{{font-size:13px}}</style></head><body><main>
    <div class="tag">NOMOBUG / MODEL RESEARCH / 21 OCTOBER 2026</div><h1>Can we estimate next week's bookings and booked hours?</h1>
    <p>Management could use this to plan team rosters and supplies. The model starts with booking entries already visible before the week and estimates later additions. Booked hours describe appointment time, not delivered work or available staff capacity.</p>
    <div class="card warning"><b>Retrospective, exploratory comparison.</b> Current surviving Calendar records were filtered by their creation and latest-update timestamps. This cannot recreate deleted, moved or earlier versions of appointments. A clean live test is still needed. We do not call 100% minus WAPE “accuracy”.</div>
    <section><h2>Results selected without looking at the later scores</h2>{table}<p>MAE is the average absolute error per forecast window. Lower is better. WAPE is total absolute error divided by total recorded outcome. The research gate requires at least 10% lower MAE than the development-selected simple baseline and a positive block-bootstrap improvement interval.</p></section>
    <section><h2>What was tested?</h2><p>144 plausible configurations across two targets and two horizons: Ridge regression, shallow Random Forest, Extra Trees and gradient boosting, with 52 weeks, 78 weeks or all available training history. All learned candidates predict late additions. Inputs include visible advance bookings, lagged bookings/hours, rolling averages, variation, seasonality and nominal festival dates. One input set also uses old regional rainfall, temperature and humidity.</p><p>Six baselines include visible bookings alone, rolling totals and rolling late-addition estimates. Validation used 13 rolling origins from January–June 2026. The selected configuration and simple comparator were frozen before assessing July–October 2026. The two-week task has overlapping outcome windows and uses a block bootstrap.</p></section>
    <section><h2>Availability checks</h2><p>{audit['eligible_recorded_booking_entries']:,} current service-like Calendar entries were retained. Inputs only include surviving records created and last updated before each forecast origin. A training outcome window is allowed only after its end and every retained event's latest update. Earlier data are reconstructed from a later snapshot, so these gates reduce leakage but cannot prove a complete historical live record.</p><p>Sales and payment forecasts were not added in this round because historical revision/settlement dates are not sufficiently trustworthy for an as-of claim. Existing sales forecasting studies remain in the project register.</p></section>{figures}
    <section><h2>Reproduce and inspect</h2><p><a href="results.json">Exact results</a> · <a href="development_leaderboard.csv">144-configuration validation table</a> · <a href="protocol.json">Predeclared protocol</a> · <a href="verification.json">Checks</a></p><p>Source hashes, selected configurations, feature names and aggregate forecast rows are stored alongside this report. Nothing was deployed or changed in the original frozen return model.</p></section></main></body></html>'''
    (OUT/'Management_Forecasts.html').write_text(content,encoding='utf-8')


def main():
    import sys
    OUT.mkdir(parents=True,exist_ok=True)
    resume='--resume-incomplete' in sys.argv
    assert not (OUT/'protocol.json').exists() or resume,'Do not silently overwrite declared research; use a separately declared experiment.'
    protected=[ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json',ROOT/'config/cp2_model_current.json']
    protocol={'declared_at_utc':now(),'script_sha256':sha(__file__),
              'sources':{str(p.relative_to(ROOT)):sha(p) for p in [SOURCE,WEATHER_SOURCE,HOLIDAY_SOURCE]},
              'protected':{str(p.relative_to(ROOT)):sha(p) for p in protected},
              'targets':TARGETS,'horizons_weeks':HORIZONS,'models':FAMILIES,'history_weeks':HISTORY,'features':GROUPS,'baselines':BASELINES,
              'configuration_count':4*(len(FAMILIES)*len(HISTORY)*len(GROUPS)+len(BASELINES)),
              'development_origins':[str(d.date()) for d in DEV],
              'assessment_origins':[str(d.date()) for d in ASSESS],
              'selection':'Lowest pooled development MAE, tie-break family/history/features; baseline independently lowest development MAE. Freeze before any later score. Refit selected fixed configuration on earlier mature rows each origin.',
              'availability':'Each current surviving feature record created AND latest-updated strictly before origin. Train outcome end <= origin and every observed event in outcome latest-updated < origin.',
              'visible_stock':'Surviving next-window records created/latest-updated before origin; not final future booking stock. Unknown old versions are not reconstructed.',
              'weather':'Reused Open-Meteo ERA5 regional proxy; last used day >=7 days before origin. No realized forecast-window weather.',
              'holidays':'Reused nominal common regional dates, incomplete substitutes/state/company closure calendar. Predetermined calendar context, not operating status.',
              'gate':'MAE >=10% lower than development-selected simple baseline and 95% two-week-block improvement lower bound >0. No deployment.',
              'scope':'Corrected adaptive historical selection after excluded v1 results were seen; no pristine holdout. No claim all possible models were tested.',
              'correction':'Only validation origins whose outcome_end <= first assessment and last_outcome_update < first assessment can select configurations. Same fixed grid. No tuning based on old scores.',
              'first_assessment_origin':'2026-07-06',
              'excluded_previous_run':{'folder':'outputs/model_validation/20261021_management_forecasts','reason':'Validation outcome latest updates after first assessment could inform selection',
                 'old_results_sha256':sha(ROOT/'outputs/model_validation/20261021_management_forecasts/results.json'),
                 'old_protocol_sha256':sha(ROOT/'outputs/model_validation/20261021_management_forecasts/protocol.json')}}
    if (OUT/'feasibility_failed_initial/protocol.json').exists():
        protocol['pre_score_feasibility_amendment']={'initial_protocol_sha256':sha(OUT/'feasibility_failed_initial/protocol.json'),
            'reason':'Initial 26-week training history retained only 3–5 matured windows at early validation origins. This failed before any model fit/score. Replaced 26-week window with 78 weeks, keeping all original validation and assessment dates and search count. Initial failure preserved.'}
    assert protocol['configuration_count']==144
    if resume:
        protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
        save(OUT/'feasibility_continuation.json',{'declared_at_utc':now(),'original_protocol_sha256':sha(OUT/'protocol.json'),
            'continuation_script_sha256':sha(__file__),'change':'Incomplete configurations with fewer than 8 timestamp-matured training windows are recorded infeasible. Never lower maturity gates. Recompute completed-task development for deterministic receipt recovery; reuse its existing assessment without refitting or re-evaluating.',
            'reason':'Next-two-week target has more late-edited outcome windows. 52-week histories have only 3–4 mature windows at early development origins.',
            'assessment_already_completed':['booking_entries_h1'],'new_scores_do_not_choose_config_feasibility':True})
    else:
        save(OUT/'protocol.json',protocol)
    data,audit=events();save(OUT/'data_audit.json',audit);weather,holidays=context()
    leader=[];all_dev=[];results=[];failures=[]
    prior_results=json.loads((OUT/'results.json').read_text(encoding='utf-8')) if resume and (OUT/'results.json').exists() else []
    for target,horizon in product(TARGETS,HORIZONS):
        task=f'{target}_h{horizon}';d=matrix(data,target,horizon,weather,holidays)
        # Direct availability examples make timestamp cutoffs inspectable without names.
        d.to_csv(OUT/f'{task}_matrix.csv',index=False)
        first_assessment=pd.Timestamp('2026-07-06')
        available_for_selection=d.outcome_end.le(first_assessment) & d.last_outcome_update.lt(first_assessment)
        dev_dates=[x for x in DEV if x in set(d.loc[available_for_selection,'origin'])]
        excluded=d[d.origin.isin(DEV)&~available_for_selection][['origin','outcome_end','last_outcome_update']]
        save(OUT/f'{task}_validation_maturity.json',{'first_assessment':str(first_assessment.date()),
            'included_origins':[str(x.date()) for x in dev_dates],'excluded_origins':excluded.to_dict('records'),
            'all_validation_labels_known_before_first_assessment':True})
        test_dates=[x for x in ASSESS if x+pd.Timedelta(weeks=horizon)<=END]
        configurations=[]
        for family,history,group in product(FAMILIES,HISTORY,GROUPS):
            configurations.append({'id':f'{family}_w{history}_{group}','family':family,'history_weeks':history,'features':group,'target':target})
        configurations += [{'id':family,'family':family,'history_weeks':1000,'features':'activity_calendar','target':target} for family in BASELINES]
        board=[]
        for index,config in enumerate(configurations):
            try:
                rows=evaluate(d,dev_dates,config,horizon,'development');score=metrics(rows)
            except ValueError as error:
                if 'Insufficient matured earlier windows' not in str(error):raise
                failures.append({'task':task,'configuration':config,'reason':str(error),'assessment_not_accessed_for_configuration':True})
                continue
            item={'task':task,'horizon_weeks':horizon,**config,**score}
            board.append(item);leader.append(item);all_dev.extend(rows)
            if index%9==0:print(f'{task} development {index+1}/{len(configurations)}',flush=True)
        key=lambda x:(x['mae'],x['family'],x['history_weeks'],x['features'])
        chosen=min(board,key=key);base=min([x for x in board if x['family'] in BASELINES],key=key)
        visible=next(x for x in board if x['family']=='visible_only')
        previous=next((r for r in prior_results if r['task']==task),None)
        if previous:
            assert chosen==previous['selected'] and base==previous['baseline'],'Completed task selection changed; stop rather than rescore.'
            results.append(previous)
            save(OUT/'results.json',results)
            print('REUSED PRIOR ASSESSMENT',task,flush=True)
            continue
        save(OUT/f'{task}_selection.json',{'frozen_at_utc':now(),'protocol_sha256':sha(OUT/'protocol.json'),'selected':chosen,'baseline':base,
                                         'feature_names':feature_columns(d,chosen['features']),'selection_used_assessment':False})
        selected_rows=evaluate(d,test_dates,chosen,horizon,'assessment')
        baseline_rows=evaluate(d,test_dates,base,horizon,'assessment')
        visible_rows=evaluate(d,test_dates,visible,horizon,'assessment')
        sm,bm,vm=metrics(selected_rows),metrics(baseline_rows),metrics(visible_rows)
        uncertainty=bootstrap(selected_rows,baseline_rows,horizon)
        improvement=1-sm['mae']/bm['mae']
        result={'task':task,'target':target,'horizon_weeks':horizon,'selected':chosen,'baseline':base,
                'assessment':sm,'baseline_assessment':bm,'visible_only_assessment':vm,
                'mae_improvement_fraction':improvement,'uncertainty':uncertainty,
                'research_gate_passed':bool(improvement>=.1 and uncertainty['baseline_minus_selected_mae_95pct_interval'][0]>0),
                'operationally_validated':False,'live_historical_state_reconstructed':False,
                'input_count':len(feature_columns(d,chosen['features']))}
        results.append(result)
        frame=pd.DataFrame(selected_rows).rename(columns={'prediction':'selected'})
        frame['baseline']=[r['prediction'] for r in baseline_rows]
        frame['visible_only']=[r['prediction'] for r in visible_rows]
        frame.to_csv(OUT/f'{task}_assessment.csv',index=False)
        save(OUT/'results.json',results)
        pd.DataFrame(leader).to_csv(OUT/'development_leaderboard_partial.csv',index=False)
        save(OUT/'infeasible_configurations.json',failures)
        print('ASSESSMENT',task,json.dumps({'selected':chosen['family'],'MAE':sm['mae'],'baseline_MAE':bm['mae'],'visible_MAE':vm['mae'],'WAPE':sm['wape']}),flush=True)
    pd.DataFrame(leader).to_csv(OUT/'development_leaderboard.csv',index=False)
    pd.DataFrame(all_dev).to_csv(OUT/'development_predictions.csv',index=False)
    assert len(leader)+len(failures)==144
    assert all(sha(ROOT/p)==h for p,h in protocol['protected'].items())
    checks={'completed_at_utc':now(),'development_configurations':len(leader),'infeasible_configurations':len(failures),'attempted_configurations':144,'selected_task_count':len(results),
            'source_hashes_unchanged':all(sha(ROOT/p)==h for p,h in protocol['sources'].items()),
            'protected_frozen_hashes_unchanged':True,'max_model_threads':2,
            'no_future_weather':True,'no_outcome_fields_in_predictors':True,'training_label_update_gate_checked':True,
            'historical_live_state_complete':False,'interpretation':'No production promotion. WAPE is error, not classification accuracy.'}
    save(OUT/'verification.json',checks)
    html_report(results,audit)


if __name__=='__main__':
    with warnings.catch_warnings(),threadpool_limits(limits=2):
        warnings.simplefilter('error',RuntimeWarning)
        main()
