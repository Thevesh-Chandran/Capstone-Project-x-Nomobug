"""Check time boundaries rather than whether a model fits its own output."""
import numpy as np
import pandas as pd
from scripts.research_additional_models import feature_row, origins, predict, supervised


def sample():
    return pd.Series(np.arange(1,121,dtype=float),index=pd.date_range('2024-06-03',periods=120,freq='W-MON'))


def test_later_outcomes_do_not_change_forecast_at_origin():
    series=sample();origin=series.index[90]
    changed=series.copy();changed.loc[changed.index>=origin]=1e9
    for name in ('last_week','mean_4','mean_8','seasonal_52','ridge','extra_trees'):
        a=predict(series,origin,4,name,'all')
        b=predict(changed,origin,4,name,'all')
        assert np.isclose(a,b,rtol=0,atol=1e-10)


def test_direct_four_week_training_targets_end_before_origin():
    history=sample().iloc[:40]
    x,y=supervised(history,4)
    assert len(y)==29
    assert y[-1]==history.iloc[-4:].sum()
    assert np.array_equal(x[-1][:8],history.iloc[28:36].to_numpy()[::-1])


def test_validation_targets_do_not_overlap_final_holdout():
    dev=origins('2026-05-04','2026-06-22',4)
    assert max(dev)+pd.Timedelta(weeks=4)<=pd.Timestamp('2026-07-20')
    test=origins('2026-07-20','2026-10-05',4)
    assert len(test)==9
    assert max(test)+pd.Timedelta(weeks=4)==pd.Timestamp('2026-10-12')


def test_seasonal_baseline_uses_past_corresponding_weeks():
    series=sample();origin=series.index[100]
    assert predict(series,origin,4,'seasonal_52','all')==series.iloc[48:52].sum()


def test_feature_vector_is_strictly_past_and_has_sixteen_inputs():
    history=np.arange(1,21,dtype=float)
    features=feature_row(history,pd.Timestamp('2026-07-20'))
    assert len(features)==16
    assert np.array_equal(features[:8],history[-8:][::-1])
