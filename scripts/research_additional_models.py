"""Bounded, reproducible additional forecasting research; never edits v5 or cloud.

Export company-level aggregates from an immutable reporting release. Select on
development origins, freeze the selection, then evaluate a separate later block.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'profound-keel-500007-s4'
LIMIT = 100 * 1024 * 1024
TARGETS = ['weekly_bookings', 'weekly_packages', 'weekly_sales_rm']
WINDOWS = ['all', 'last_52_weeks', '2026_only']
BASELINES = ['last_week', 'mean_4', 'mean_8', 'seasonal_52']
MODELS = ['ses', 'holt_damped', 'ridge', 'poisson', 'random_forest', 'extra_trees',
          'hist_gradient_boosting', 'hist_gradient_boosting_poisson', 'catboost']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')


def export(folder, protocol):
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT, location='asia-southeast1')
    prefix = protocol['source_release']
    receipts = []
    def query(sql):
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
        if (dry.total_bytes_processed or 0) > LIMIT:
            raise ValueError('Query exceeds 100 MiB')
        job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=LIMIT))
        rows = [dict(r.items()) for r in job.result(timeout=120)]
        receipts.append({'job_id': job.job_id, 'bytes_processed': job.total_bytes_processed,
                         'sql': sql, 'row_count': len(rows)})
        return rows
    try:
        bookings = query(f'''SELECT event_date_local AS date, COUNT(*) AS bookings,
            COUNTIF(warranty_claim_candidate) AS warranty_signals,
            COUNTIF(event_created_ts IS NULL) AS missing_created,
            COUNTIF(event_updated_ts > TIMESTAMP(event_date_local, 'Asia/Kuala_Lumpur')) AS edited_after_anchor
            FROM `{PROJECT}.{prefix}_gold.calendar_programme_service_facts`
            WHERE event_date_local <= DATE '2026-10-11' GROUP BY date ORDER BY date''')
        sales = query(f'''SELECT closed_date AS date, COUNT(*) AS packages,
            SUM(sale_total_rm) AS sales_rm,
            COUNTIF(closed_date_year_source != 'entry_timestamp') AS inferred_year_rows,
            COUNTIF(sale_total_rm IS NULL) AS missing_amount_rows
            FROM `{PROJECT}.{prefix}_gold.sales_package_facts` WHERE include_in_sale_count
            GROUP BY date ORDER BY date''')
        quality = query(f'''SELECT closed_date_year_source, COUNT(*) AS sale_rows,
            COUNTIF(closed_date IS NULL) AS missing_date_rows, COUNTIF(sale_total_rm IS NULL) AS missing_amount_rows
            FROM `{PROJECT}.{prefix}_gold.sales_package_facts` WHERE include_in_sale_count
            GROUP BY closed_date_year_source ORDER BY closed_date_year_source''')
        for name, rows in [('daily_bookings', bookings), ('daily_sales', sales)]:
            pd.DataFrame(rows).to_csv(folder/(name+'.csv'), index=False)
        receipt = {'extracted_at_utc': datetime.now(timezone.utc).isoformat(), 'release': prefix,
                   'queries': receipts, 'sales_date_quality': quality}
        save(folder/'source_receipt.json', receipt)
    finally:
        client.close()


def weekly_series(folder):
    events = pd.read_csv(folder/'daily_bookings.csv', parse_dates=['date'])
    sales = pd.read_csv(folder/'daily_sales.csv', parse_dates=['date'])
    # Count and disclose missing dates; do not place unknown dates into a week.
    undated = int(sales.loc[sales.date.isna(), 'packages'].sum())
    sales = sales[sales.date.notna()]
    frames = {}
    audit = {'undated_sales_excluded': undated, 'targets': {}}
    for target, frame, column in [('weekly_bookings',events,'bookings'),
                                  ('weekly_packages',sales,'packages'),('weekly_sales_rm',sales,'sales_rm')]:
        # Initial observed week is partial/left-censored; start next Monday.
        first = frame.date.min().normalize()
        start = first + pd.Timedelta(days=(7-first.weekday()) % 7)
        if start == first:
            start += pd.Timedelta(days=7)
        daily = frame.groupby('date')[column].sum().reindex(pd.date_range(start,'2026-10-11'),fill_value=0)
        series = daily.resample('W-MON',label='left',closed='left').sum()
        frames[target] = series.astype(float)
        audit['targets'][target] = {'first_week': str(series.index[0].date()), 'last_week': str(series.index[-1].date()),
            'weeks': len(series), 'total': float(series.sum()), 'zero_weeks': int((series==0).sum()),
            'year_counts': {str(year): {'weeks':len(part),'total':float(part.sum())} for year,part in series.groupby(series.index.year)}}
    save(folder/'data_audit.json', audit)
    pd.DataFrame(frames).to_csv(folder/'weekly_targets.csv',index_label='week_start')
    return frames


def feature_row(history, origin):
    y = np.asarray(history, dtype=float)
    if len(y) < 8:
        raise ValueError('Need eight strictly past weeks')
    week = origin.isocalendar().week
    return np.r_[y[-8:][::-1], [np.mean(y[-4:]),np.mean(y[-8:]),np.std(y[-8:]),
        np.min(y[-8:]),np.max(y[-8:]),(y[-1]-y[-4])/3,
        math.sin(2*math.pi*week/52.18),math.cos(2*math.pi*week/52.18)]]


def supervised(history, horizon):
    x, y = [], []
    values = history.to_numpy()
    for i in range(8,len(history)-horizon+1):
        x.append(feature_row(values[:i],history.index[i]))
        y.append(values[i:i+horizon].sum())
    return np.asarray(x), np.asarray(y)


def smoothing(values, horizon, damped=False):
    values = np.asarray(values,float)
    def compute(params, forecast=False):
        alpha = params[0]
        beta, phi = (params[1], params[2]) if damped else (0,0)
        level = values[0]; trend = values[1]-values[0] if damped else 0
        loss = 0.0
        for actual in values[1:]:
            expected = level+phi*trend
            loss += (actual-expected)**2
            new_level = alpha*actual+(1-alpha)*expected
            trend = beta*(new_level-level)+(1-beta)*phi*trend
            level = new_level
        if forecast:
            return float(sum(max(0,level+sum(phi**k for k in range(1,h+1))*trend) for h in range(1,horizon+1)))
        return loss/max(1,len(values)-1)
    x0,bounds = ([.3,.1,.9],[(.01,.99),(.01,.99),(.7,.99)]) if damped else ([.3],[(.01,.99)])
    fit = minimize(compute,x0,bounds=bounds,method='L-BFGS-B',options={'maxiter':80})
    return compute(fit.x,True)


def estimator(name):
    if name=='ridge': return make_pipeline(StandardScaler(),Ridge(alpha=10))
    if name=='poisson': return make_pipeline(StandardScaler(),PoissonRegressor(alpha=1,max_iter=300))
    if name=='random_forest': return RandomForestRegressor(n_estimators=100,max_depth=4,min_samples_leaf=4,random_state=20261014,n_jobs=2)
    if name=='extra_trees': return ExtraTreesRegressor(n_estimators=100,max_depth=4,min_samples_leaf=4,random_state=20261014,n_jobs=2)
    if name.startswith('hist_gradient'):
        return HistGradientBoostingRegressor(loss='poisson' if name.endswith('poisson') else 'squared_error',max_iter=80,max_leaf_nodes=7,min_samples_leaf=5,l2_regularization=5,early_stopping=False,random_state=20261014)
    if name=='catboost':
        from catboost import CatBoostRegressor
        return CatBoostRegressor(iterations=100,depth=3,learning_rate=.05,l2_leaf_reg=10,verbose=False,thread_count=2,random_seed=20261014,allow_writing_files=False)
    raise ValueError(name)


def predict(series, origin, horizon, model, window):
    history = series[series.index < origin]
    if window=='last_52_weeks': history = history.iloc[-52:]
    if window=='2026_only': history = history[history.index >= '2026-01-01']
    if len(history)<12: raise ValueError('Insufficient training history')
    vals = history.to_numpy()
    if model=='last_week': return float(vals[-1]*horizon)
    if model=='mean_4': return float(vals[-4:].mean()*horizon)
    if model=='mean_8': return float(vals[-8:].mean()*horizon)
    if model=='seasonal_52':
        if len(vals)<52: raise ValueError('Need 52 observed training weeks')
        # Last year's corresponding future weeks, all strictly before origin.
        return float(vals[-52:-52+horizon].sum())
    if model in ('ses','holt_damped'): return smoothing(vals,horizon,model=='holt_damped')
    x,y = supervised(history,horizon)
    if len(y)<6: raise ValueError('Insufficient supervised rows')
    fitted = estimator(model)
    # Scale the target for stability; preserves relative comparison within task.
    scale = max(1,float(np.mean(y)))
    fitted.fit(x,y/scale)
    value = float(fitted.predict(feature_row(vals,origin).reshape(1,-1))[0]*scale)
    if not np.isfinite(value): raise ValueError('Nonfinite forecast')
    return max(0,value)


def origins(start,end,horizon):
    return [d for d in pd.date_range(start,end,freq='W-MON') if d+pd.Timedelta(weeks=horizon)<=pd.Timestamp('2026-10-12')]


def metrics(rows):
    actual=np.array([r['actual'] for r in rows]);prediction=np.array([r['prediction'] for r in rows]);error=prediction-actual
    return {'origins':len(rows),'mae':float(np.abs(error).mean()),'rmse':float(np.sqrt(np.mean(error**2))),
            'wape':float(np.abs(error).sum()/actual.sum()) if actual.sum() else None,
            'bias':float(error.mean()),'actual_mean':float(actual.mean())}


def block_difference(candidate,baseline,horizon):
    diffs=np.array([abs(a['prediction']-a['actual'])-abs(b['prediction']-b['actual']) for a,b in zip(candidate,baseline)])
    rng=np.random.default_rng(20261014);n=len(diffs);block=min(n,max(2,horizon));samples=[]
    for _ in range(4000):
        idx=np.concatenate([(s+np.arange(block))%n for s in rng.integers(0,n,size=math.ceil(n/block))])[:n]
        samples.append(diffs[idx].mean())
    return {'mae_difference_90pct_interval':list(map(float,np.quantile(samples,[.05,.95]))),
            'origin_win_fraction':float((diffs<0).mean()),'block_length':block,
            'warning':'Small dependent sample; exploratory interval, not multiplicity-adjusted evidence'}


def benchmark(folder, protocol):
    frames=weekly_series(folder)
    predictions=[]; failures=[]; leaderboards=[];selection={}
    with threadpool_limits(limits=2):
        for target,series in frames.items():
            for h in protocol['horizons_weeks']:
                key=f'{target}_h{h}'
                dev_origins=origins(*protocol['development_origins'],h)
                test_origins=origins(protocol['holdout_origins_start'],'2026-10-05',h)
                candidates=[]
                for name in BASELINES+MODELS:
                    # Poisson is not a meaningful likelihood for monetary values.
                    if target.endswith('_rm') and name in ('poisson','hist_gradient_boosting_poisson'):continue
                    for window in WINDOWS:
                        rows=[]
                        for origin in dev_origins:
                            try:
                                p=predict(series,origin,h,name,window)
                                actual=float(series[(series.index>=origin)&(series.index<origin+pd.Timedelta(weeks=h))].sum())
                                rows.append({'target':target,'horizon':h,'model':name,'window':window,'phase':'development','origin':str(origin.date()),'actual':actual,'prediction':p})
                            except Exception as error:
                                failures.append({'task':key,'model':name,'window':window,'origin':str(origin.date()),'error':str(error)})
                        if len(rows)==len(dev_origins):
                            score=metrics(rows);item={'target':target,'horizon':h,'model':name,'window':window,**score}
                            candidates.append((item,rows));leaderboards.append(item);predictions.extend(rows)
                if not candidates:raise ValueError('No complete candidates for '+key)
                candidates.sort(key=lambda r:(r[0]['mae'],r[0]['model'],r[0]['window']))
                best=candidates[0];base=min((r for r in candidates if r[0]['model'] in BASELINES),key=lambda r:r[0]['mae'])
                selection[key]={'selected':best[0],'baseline':base[0],'frozen_at_utc':datetime.now(timezone.utc).isoformat()}
                # This file is committed to disk before any holdout labels are scored.
                save(folder/'development_selection.json',selection)
                print(json.dumps({'task':key,'development_winner':best[0]['model'],'window':best[0]['window'],'mae':best[0]['mae']}),flush=True)
                scored=[]
                for selected in (best,base):
                    item,dev_rows=selected;rows=[]
                    residuals=np.array([abs(r['actual']-r['prediction']) for r in dev_rows])
                    radius=float(np.quantile(residuals,.9,method='higher'))
                    for origin in test_origins:
                        p=predict(series,origin,h,item['model'],item['window'])
                        actual=float(series[(series.index>=origin)&(series.index<origin+pd.Timedelta(weeks=h))].sum())
                        rows.append({'target':target,'horizon':h,'model':item['model'],'window':item['window'],
                            'phase':'holdout','origin':str(origin.date()),'actual':actual,'prediction':p,
                            'interval_lower':max(0,p-radius),'interval_upper':p+radius})
                    predictions.extend(rows);scored.append(rows)
                result=selection[key];result['holdout']=metrics(scored[0]);result['baseline_holdout']=metrics(scored[1])
                result.update(block_difference(*scored,h))
                result['holdout_mae_improvement']=1-result['holdout']['mae']/result['baseline_holdout']['mae'] if result['baseline_holdout']['mae'] else 0
                result['development_mae_improvement']=1-best[0]['mae']/base[0]['mae'] if base[0]['mae'] else 0
                result['holdout_interval_coverage']=float(np.mean([r['interval_lower']<=r['actual']<=r['interval_upper'] for r in scored[0]]))
                result['holdout_interval_mean_width']=float(np.mean([r['interval_upper']-r['interval_lower'] for r in scored[0]]))
                result['research_gate_passed']=bool(result['holdout_mae_improvement']>=.1 and result['development_mae_improvement']>0 and result['origin_win_fraction']>=.6 and result['mae_difference_90pct_interval'][1]<0)
                result['operationally_validated']=False
                print(json.dumps({'task':key,'holdout':result['holdout'],'improvement':result['holdout_mae_improvement'],'gate':result['research_gate_passed']}),flush=True)
    pd.DataFrame(predictions).to_csv(folder/'predictions.csv',index=False)
    pd.DataFrame(leaderboards).sort_values(['target','horizon','mae']).to_csv(folder/'development_leaderboard.csv',index=False)
    save(folder/'fit_failures.json',failures);save(folder/'results.json',selection)
    return selection


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='outputs/additional_model_research/20261014');parser.add_argument('--reuse-export',action='store_true');args=parser.parse_args()
    folder=(ROOT/args.output).resolve()
    if not folder.is_relative_to(ROOT/'outputs'):raise ValueError('Research exports must remain under ignored outputs')
    folder.mkdir(parents=True,exist_ok=True)
    protocol_path=ROOT/'config/cp2_additional_model_research_v1.json';protocol=json.loads(protocol_path.read_text())
    protected=[ROOT/'config/cp2_model_current.json',ROOT/'config/cp2_october10_cohort.json',ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json']
    before={str(p.relative_to(ROOT)):digest(p) for p in protected}
    save(folder/'run_manifest.json',{'started_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':digest(protocol_path),
        'script_sha256':digest(__file__),'protected_hashes_before':before,
        'versions':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scikit-learn','scipy','catboost']}})
    if not args.reuse_export:export(folder,protocol)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        benchmark(folder,protocol)
        save(folder/'fit_warnings.json',[str(w.message) for w in captured])
    after={str(p.relative_to(ROOT)):digest(p) for p in protected}
    if before!=after:raise ValueError('Protected model/protocol changed')
    save(folder/'protected_artifact_check.json',{'unchanged':True,'hashes':after})


if __name__=='__main__':main()
