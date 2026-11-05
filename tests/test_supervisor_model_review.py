import numpy as np
import pandas as pd
from scipy.stats import pointbiserialr,spearmanr
from scripts.build_supervisor_model_review import associations

def test_numeric_associations_match_independent_scipy_calculations():
    f=pd.DataFrame({'x':[1.,2.,3.,4.,5.,np.nan],'y':[False,False,True,False,True,True]})
    actual=associations(f,['x'],'y').iloc[0]
    pair=f.dropna()
    assert actual.available_rows==5
    assert np.isclose(actual.pearson_r,pointbiserialr(pair.y.astype(int),pair.x).statistic)
    assert np.isclose(actual.spearman_rho,spearmanr(pair.x,pair.y.astype(int)).statistic)

def test_constant_predictor_has_undefined_correlation_not_zero_evidence():
    f=pd.DataFrame({'x':[1.,1.,1.],'y':[False,True,False]})
    actual=associations(f,['x'],'y').iloc[0]
    assert np.isnan(actual.pearson_r) and np.isnan(actual.spearman_rho)

def test_missing_predictor_does_not_impute_zero_for_association():
    f=pd.DataFrame({'x':[np.nan,np.inf,2.,4.],'y':[True,False,False,True]})
    actual=associations(f,['x'],'y').iloc[0]
    assert actual.available_rows==2
    assert actual.missing_pct==50
