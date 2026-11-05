import pandas as pd
import pytest
from scripts.test_interservice_weather import interval_features


def daily():
    return pd.DataFrame({'precipitation_sum':[2.,12.,999.],
       'temperature_2m_mean':[26.,28.,99.],'relative_humidity_2m_mean':[70.,80.,99.],
       'soil_moisture_0_to_7cm_mean':[.2,.4,.9]},index=pd.date_range('2026-01-01',periods=3))


def test_excludes_later_service_day_and_accounts_for_duration():
    x=interval_features(daily(),pd.Timestamp('2026-01-01'),pd.Timestamp('2026-01-03'))
    assert x['rain_total_mm']==14 and x['rain_per_day_mm']==7
    assert x['heavy_rain_days_10mm']==1 and x['temperature_mean_c']==27


def test_incomplete_interval_is_unknown_not_zero():
    assert interval_features(daily().iloc[:1],pd.Timestamp('2026-01-01'),pd.Timestamp('2026-01-03')) is None
    d=daily();d.loc[d.index[0],'precipitation_sum']=float('nan')
    assert interval_features(d,pd.Timestamp('2026-01-01'),pd.Timestamp('2026-01-03')) is None


def test_non_increasing_stages_rejected():
    with pytest.raises(ValueError):
        interval_features(daily(),pd.Timestamp('2026-01-02'),pd.Timestamp('2026-01-01'))
