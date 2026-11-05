import numpy as np
import pandas as pd
from scripts.freeze_age_rain_candidate import rainfall_additions

def setup_rows():
    frame=pd.DataFrame({'sales_record_id':['s','s'],'address_hash':['a','a'],
        'anchor_date':pd.to_datetime(['2025-01-01','2025-01-11']),'service_number':[1,2],
        'prior_7d_precipitation_mm':[7.,7.]})
    locations=pd.DataFrame({'address_hash':['a'],'latitude':[3.1],'longitude':[101.7]})
    daily=pd.DataFrame({'precipitation_sum':1.},index=pd.date_range('2024-11-01','2025-02-01'))
    return frame,locations,{(3.1,101.7):daily}

def test_only_completed_interval_and_pre_first_rain_used():
    f,loc,w=setup_rows();a=rainfall_additions(f,loc,w)
    assert np.isnan(a.previous_interval_rain_mean_mm.iloc[0])
    assert a.previous_interval_rain_mean_mm.iloc[1]==1 and a.previous_interval_days.iloc[1]==10
    assert a.before_first_7d_rain_mean_mm.iloc[1]==1 and a.before_first_30d_rain_mean_mm.iloc[1]==1
    w[(3.1,101.7)].loc['2025-01-11':,'precipitation_sum']=999
    pd.testing.assert_frame_equal(a,rainfall_additions(f,loc,w))

def test_ambiguous_prior_stage_stays_unknown():
    f,loc,w=setup_rows();duplicate=f.iloc[[0]].copy();duplicate.anchor_date=pd.to_datetime('2025-01-02')
    f=pd.concat([f,duplicate],ignore_index=True);a=rainfall_additions(f,loc,w)
    assert a.interval_rain_unknown.iloc[1]==1 and np.isnan(a.previous_interval_rain_mean_mm.iloc[1])

def test_weather_cell_disagreement_stays_unknown():
    f,loc,w=setup_rows();f.loc[1,'prior_7d_precipitation_mm']=123
    a=rainfall_additions(f,loc,w);assert a.interval_rain_unknown.iloc[1]==1
