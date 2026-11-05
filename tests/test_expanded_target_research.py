import numpy as np
import pandas as pd
from scripts.research_expanded_targets import weather_features, split_repeat, weekly_matrix, repeat_data

def weather():
    index=pd.date_range('2023-01-01','2026-12-31')
    return pd.DataFrame({'precipitation_sum':np.ones(len(index)),'temperature_2m_mean':27.,'relative_humidity_2m_mean':80.},index=index)

def test_weather_excludes_recent_and_future_data():
    w=weather();date=pd.Timestamp('2025-01-01');before=weather_features(w,date)
    w.loc[w.index>=date-pd.Timedelta(days=7),:]=9999
    assert weather_features(w,date)==before
    assert before['rain_7']==7 and before['rain_28']==28

def test_maturity_purge_and_customer_disjointness():
    d=pd.DataFrame({'first_date':pd.to_datetime(['2024-01-01','2024-12-15','2025-01-01']),
        'outcome_end':pd.to_datetime(['2024-04-01','2025-03-15','2025-04-01']),'customer_hash':['a','b','c']})
    train,test=split_repeat(d,'2025-01-01','2025-02-01','all_history')
    assert train.customer_hash.tolist()==['a'] and test.customer_hash.tolist()==['c']

def test_linked_upsell_is_not_another_programme():
    def sale(date,programme,amount):return {'date':date,'programme_id':programme,'sales_rm':amount,'package':'3x','pest':'ants','premise':'house'}
    source=[{'customer_key':'a','identity_status':'matched','sales':[sale('2024-06-01','one',100),sale('2024-06-10','one',200),sale('2024-09-01','two',400)]}]
    d,_=repeat_data(source,30,weather());assert d.label.iloc[0]==0 and np.isclose(d.log_initial_sales.iloc[0],np.log1p(100))
    d,_=repeat_data(source,180,weather());assert d.label.iloc[0]==1

def test_forecast_inputs_do_not_see_current_or_future_actual():
    dates=pd.date_range('2024-01-01',periods=80,freq='W-MON');s=pd.Series(np.arange(80.),index=dates)
    before=weekly_matrix(s,weather());s.loc[dates[50]:]=99999
    after=weekly_matrix(s,weather());cols=[c for c in before if c not in ['date','actual']]
    pd.testing.assert_series_equal(before.loc[before.date.eq(dates[50]),cols].iloc[0],after.loc[after.date.eq(dates[50]),cols].iloc[0])

def test_customer_history_ignores_future_sale_features():
    from scripts.research_customer_history_targets import dataset,features,partitions
    def sale(date,key,amount):return {'date':date,'programme_id':key,'sales_rm':amount,'package':'1x','pest':'ants','premise':'house'}
    source=[{'customer_key':'a','identity_status':'matched','sales':[sale('2024-03-01','one',100),sale('2024-07-01','two',200),sale('2024-07-20','two',300),sale('2024-08-01','three',400)]}]
    before=dataset(source,90,weather())
    source[0]['sales'][2]['sales_rm']=999999;source[0]['sales'][3]['package']='Future only'
    after=dataset(source,90,weather());date=pd.Timestamp('2024-07-01');cols=features('history_weather')
    pd.testing.assert_series_equal(before.loc[before.date.eq(date),cols].iloc[0],after.loc[after.date.eq(date),cols].iloc[0])
    row=before.loc[before.date.eq(date)].iloc[0]
    assert row.previous_programmes==1 and row.past_average_sale==100 and row.label==1
    assert len(before)==3
