import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform
from scripts.test_age_holiday_predictors import holiday_features,age_at_locations
from scripts.test_holiday_forecasts import weekly_festivals

def test_nominal_holiday_dates_and_counts():
    dates=pd.Series(pd.to_datetime(['2025-03-31','2025-04-01','2025-04-02','2023-12-01']))
    d=holiday_features(dates)
    assert d.festival_day.tolist()[:3]==[1,1,0]
    assert d.festival_days_next_7.iloc[0]==1
    assert d.festival_days_previous_7.iloc[2]==2
    assert np.isnan(d.festival_day.iloc[3])

def test_forecast_festival_counts_are_known_calendar_not_outcome():
    d=weekly_festivals(pd.Timestamp('2025-03-31'))
    assert d['festival_days_next_week']==2 and d['festival_days_previous_week']==0

def test_age_sampling_accepts_consistent_cells_and_rejects_nodata(tmp_path):
    x,y=transform('EPSG:4326','ESRI:54009',[101.7],[3.1]);x=x[0];y=y[0]
    a=np.full((5,5),6,dtype=np.uint8);p=tmp_path/'age.tif'
    kw=dict(driver='GTiff',height=5,width=5,count=1,dtype='uint8',crs='ESRI:54009',transform=from_origin(x-2500,y+2500,1000,1000),nodata=255)
    locations=pd.DataFrame([{'address_hash':'a','longitude':101.7,'latitude':3.1}])
    with rasterio.open(p,'w',**kw) as s:s.write(a,1)
    found,coverage=age_at_locations(locations,p);assert found=={'a':6}
    a[:]=255
    with rasterio.open(p,'w',**kw) as s:s.write(a,1)
    found,coverage=age_at_locations(locations,p)
    assert found=={} and coverage['non_built_or_nodata']==1
