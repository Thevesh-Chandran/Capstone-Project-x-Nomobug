"""Selected planning engine. Formulas ported from corrected research v2.
No candidate selection occurs here; configurations are fixed in the protocol.
"""
import math,re
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor,RandomForestRegressor,HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
SEED=20261021
TARGETS=['booking_entries','booked_hours']


def available_past(data, origin, length=13):
    known = data[data.available.lt(origin) & data.start.lt(origin)]
    index = pd.date_range(origin-pd.Timedelta(weeks=length), origin-pd.Timedelta(weeks=1), freq='W-MON')
    return known.groupby('week').agg(booking_entries=('unit','sum'),booked_hours=('hours','sum')).reindex(index,fill_value=0)

def matrix(data, target, horizon, weather, holidays, start, end):
    rows=[]
    for origin in pd.date_range(start,end-pd.Timedelta(weeks=horizon),freq='W-MON'):
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
