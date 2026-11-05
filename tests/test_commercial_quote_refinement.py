import numpy as np
import pandas as pd
from scripts.research_commercial_quote_refinement import extract_size,pipeline

def test_explicit_dimensions_have_units_and_convert_to_sqft():
    assert extract_size("Size: 19' x 70'")['area_sqft']==1330
    assert extract_size('Saiz: 20x40 ft')['area_sqft']==800
    assert extract_size('Size: 25ft x 17ft')['area_sqft']==425
    assert extract_size('Size: 2k sqft')['area_sqft']==2000
    assert abs(extract_size('Size: 3m x 4m')['area_sqft']-129.17)<0.01

def test_ambiguous_or_mixed_dimensions_remain_unknown():
    for text in ['Saiz: 20x70','Size: 20x70/75','Size: 20ft x 30m','Address: 20ft x 30ft','Size: 7037m x 4399m','Size: 1000 sqft, 20x40ft']:
        assert np.isnan(extract_size(text)['area_sqft']),text

def test_conflicting_explicit_areas_not_resolved_by_one_dimension():
    assert np.isnan(extract_size('Size: 1000sqft; upstairs 2000sqft; 20x50ft')['area_sqft'])

def test_unknown_floor_does_not_become_zero():
    assert np.isnan(extract_size('Address: 10th floor, office tower')['floors_mentioned'])
    assert extract_size('Size: 7500 sqft (3 floors)')['floors_mentioned']==3

def test_size_imputation_uses_training_only():
    frame=pd.DataFrame({'sessions':[1.]*20,'log_area_sqft':list(np.arange(10.))+[np.nan]*10})
    model=pipeline(frame,list(frame.columns),'Ridge').fit(frame,np.arange(20.)+100)
    imputer=model.estimator_.regressor_.steps[0][1].named_transformers_['numbers'].steps[0][1]
    assert imputer.statistics_[1]==4.5
    model.predict(pd.DataFrame({'sessions':[1.],'log_area_sqft':[10000.]}))
    assert imputer.statistics_[1]==4.5
