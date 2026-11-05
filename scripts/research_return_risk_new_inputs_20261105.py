"""Do inputs the return-risk model does not use yet add anything? (5 November 2026)

Same data, splits and model family as research_return_risk_20261103.py (v1).
New inputs, all known on the service date:
  team      calendar (team) the job is on, and that team's return rate on services
            whose 30-day windows had closed before this service
  timing    booked job length (hours), all-day flag, days booked ahead, weekend job
  sales     salesperson (PIC) prior return rate, recorded returning client, monthly billing
Selection uses validation only. The test block (May 2026 on) was already used to report
v1, so the test comparison is a second look, not an untouched test. v1 is not changed.

  python scripts/research_return_risk_new_inputs_20261105.py --data <dataset_input.json>
      --calendar <calendar.csv> --sales <sales.csv> --out <folder>
calendar.csv: silver.calendar_events calendar_event_row, calendar_name, start_raw, end_raw,
created_raw, is_all_day. sales.csv: silver.sales sales_record_id, pic_raw,
acquisition_relationship_raw, billing_arrangement_raw.
"""
import argparse, json, os, hashlib
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, average_precision_score

p = argparse.ArgumentParser()
for a in ('--data', '--calendar', '--sales', '--out'): p.add_argument(a, required=True)
A = p.parse_args(); os.makedirs(A.out, exist_ok=True)
if os.path.exists(os.path.join(A.out, 'results.json')): raise SystemExit('Completed study exists; never overwrite it')
Y = 'warranty_signal_within_30d'

v = json.load(open(A.data)); df = pd.DataFrame(v['records'], columns=v['columns'])
for c in ['anchor_date', 'outcome_end_date']: df[c] = pd.to_datetime(df[c])
num = ['service_number', 'package_sessions_recorded', 'sale_total_rm', 'days_since_previous_service',
       'prior_property_warranty_claims', 'prior_package_warranty_claims', 'prior_property_claims_90d', 'anchor_event_row']
for c in num: df[c] = pd.to_numeric(df[c], errors='coerce')
df[Y] = df[Y].astype(int)
df['final'] = (df.service_number >= df.package_sessions_recorded).astype(int)
df['res'] = (df.premise_type == 'RESIDENTIAL').astype(int)

cal = pd.read_csv(A.calendar)
cal = cal.drop_duplicates('calendar_event_row').set_index('calendar_event_row')
sales = pd.read_csv(A.sales, dtype=str).drop_duplicates('sales_record_id').set_index('sales_record_id')
e = cal.reindex(df.anchor_event_row)
start = pd.to_datetime(e.start_raw.values, utc=True, errors='coerce')
end = pd.to_datetime(e.end_raw.values, utc=True, errors='coerce')
created = pd.to_datetime(e.created_raw.values, utc=True, errors='coerce')
df['team'] = e.calendar_name.fillna('unknown').values
s = sales.reindex(df.sales_record_id)
df['pic'] = s.pic_raw.fillna('').str.strip().str.upper().replace('', 'unknown').values
coverage = {'calendar_matched': float(pd.notna(e.calendar_name.values).mean()),
            'sales_matched': float(pd.notna(s.pic_raw.values).mean())}

def prior_rate(key, prior=20):
    """Return rate of this key's earlier services whose windows closed before this service.
    Shrunk toward the overall prior-period rate so small groups do not swing."""
    out = np.full(len(df), np.nan); order = np.argsort(df.anchor_date.values, kind='stable')
    ends = df.outcome_end_date.values; dates = df.anchor_date.values; yv = df[Y].values; k = df[key].values
    for i in order:
        done = ends < dates[i]
        if not done.any(): continue
        base = yv[done].mean(); same = done & (k == k[i])
        out[i] = (yv[same].sum() + prior * base) / (same.sum() + prior)
    return out

F = pd.DataFrame(index=df.index)
F['final_residential'] = df.res * df.final; F['final_service'] = df.final; F['residential'] = df.res
F['three_service_programme'] = (df.package_sessions_recorded == 3).astype(float)
F['first_service'] = (df.service_number == 1).astype(float)
F['log_sale_rm'] = np.log1p(df.sale_total_rm.fillna(0))
d = df.days_since_previous_service
F['gap_missing'] = d.isna().astype(float); F['gap_days_capped'] = d.fillna(0).clip(0, 120)
F['property_past_claims'] = df.prior_property_warranty_claims.fillna(0).clip(0, 4)
F['programme_past_claims'] = df.prior_package_warranty_claims.fillna(0).clip(0, 3)
F['property_claims_90d'] = df.prior_property_claims_90d.fillna(0).clip(0, 3)
pc = df.pest_category.fillna('').str.lower()
F['cockroach_only'] = pc.str.strip().isin(['lipas']).astype(float)
F['includes_rodent'] = pc.str.contains('tikus').astype(float)
V1 = list(F.columns)  # identical to return_risk_v1 inputs

F['team_prior_rate'] = prior_rate('team')
F['team_prior_rate'] = F.team_prior_rate.fillna(np.nanmedian(F.team_prior_rate))
teams = [t for t in df.team.value_counts().index if t != 'unknown']
for t in teams[1:]: F['team_' + hashlib.sha1(t.encode()).hexdigest()[:6]] = (df.team == t).astype(float)
TEAM = ['team_prior_rate'] + [c for c in F.columns if c.startswith('team_') and c != 'team_prior_rate']
hours = ((end - start).total_seconds() / 3600)
F['job_hours'] = pd.Series(hours, index=df.index).clip(0, 10).fillna(np.nanmedian(hours))
F['all_day'] = e.is_all_day.astype(str).str.lower().eq('true').astype(float).values
ahead = ((start - created).total_seconds() / 86400)
F['days_booked_ahead'] = pd.Series(ahead, index=df.index).clip(0, 60).fillna(0)
F['weekend_job'] = df.anchor_date.dt.dayofweek.isin([5, 6]).astype(float)
TIMING = ['job_hours', 'all_day', 'days_booked_ahead', 'weekend_job']
F['pic_prior_rate'] = prior_rate('pic')
F['pic_prior_rate'] = F.pic_prior_rate.fillna(np.nanmedian(F.pic_prior_rate))
F['returning_client'] = s.acquisition_relationship_raw.fillna('').str.upper().str.contains(r'\b(?:OLD|RETURNING)\b').astype(float).values
F['monthly_billing'] = s.billing_arrangement_raw.fillna('').str.upper().str.contains('MONTH').astype(float).values
SALES = ['pic_prior_rate', 'returning_client', 'monthly_billing']

CAND = {'v1 inputs': V1, '+team': V1 + TEAM, '+timing': V1 + TIMING, '+sales': V1 + SALES,
        '+team+timing': V1 + TEAM + TIMING, '+all new': V1 + TEAM + TIMING + SALES}

dev = df.anchor_date <= '2025-09-30'; val = (df.anchor_date >= '2025-11-01') & (df.anchor_date <= '2026-03-31')
test = df.anchor_date >= '2026-05-01'; g = df.sales_record_id
dev = dev & ~g.isin(g[val | test]); val = val & ~g.isin(g[test])
assert df.outcome_end_date[dev].max() < pd.Timestamp('2025-11-01') and df.outcome_end_date[val].max() < pd.Timestamp('2026-05-01')
y = df[Y].values

def cap(yy, pp, f=.2):
    k = max(1, int(round(len(pp) * f))); i = np.argsort(-pp, kind='stable')[:k]; return float(yy[i].sum() / yy.sum())
def fit(cols, C, mask):
    m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=5000)); m.fit(F.loc[mask, cols], y[mask]); return m

rows = []
for name, cols in CAND.items():
    for C in [0.03, 0.1, 0.3, 1.0]:
        pv = fit(cols, C, dev).predict_proba(F.loc[val, cols])[:, 1]
        rows.append({'set': name, 'C': C, 'val_auc': roc_auc_score(y[val], pv), 'val_ap': average_precision_score(y[val], pv), 'val_cap20': cap(y[val], pv)})
sel = pd.DataFrame(rows)
best_per_set = sel.sort_values(['val_ap', 'val_auc'], ascending=False).groupby('set', sort=False).head(1)
chosen = best_per_set.iloc[0]
print(best_per_set.round(3).to_string(index=False)); print('CHOSEN on validation:', chosen['set'], chosen['C'])

fitmask = dev | val; yt = y[test]; res = {}
gr = df.sales_record_id[test].values; ug = np.unique(gr); rs = np.random.RandomState(7)
preds = {}
for _, r in best_per_set.iterrows():
    cols = CAND[r['set']]; pt = fit(cols, r['C'], fitmask).predict_proba(F.loc[test, cols])[:, 1]; preds[r['set']] = pt
    res[r['set']] = {'C': float(r['C']), 'val_ap': float(r['val_ap']), 'test_auc': roc_auc_score(yt, pt), 'test_ap': average_precision_score(yt, pt), 'test_cap20': cap(yt, pt)}
diffs = {k: [] for k in preds if k != 'v1 inputs'}
for _ in range(1000):
    pick = rs.choice(ug, len(ug)); idx = np.concatenate([np.flatnonzero(gr == u) for u in pick])
    if yt[idx].sum() == 0: continue
    for k in diffs: diffs[k].append(average_precision_score(yt[idx], preds[k][idx]) - average_precision_score(yt[idx], preds['v1 inputs'][idx]))
for k, dd in diffs.items(): res[k]['test_ap_gain_vs_v1_95ci'] = np.percentile(dd, [2.5, 50, 97.5]).round(4).tolist()
out = {'chosen_on_validation': chosen['set'], 'coverage': coverage, 'test_services': int(test.sum()), 'test_returns': int(yt.sum()),
       'teams': len(teams), 'results': res, 'validation_table': rows,
       'note': 'Test block was already used to report v1; this is a second look. Selection used validation only.'}
json.dump(out, open(os.path.join(A.out, 'results.json'), 'w'), indent=1, default=float)
print(pd.DataFrame(res).T.round(3).to_string()); print('coverage', coverage)
