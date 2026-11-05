import numpy as np
from scripts.research_calendar_quote_sizes import extract

def test_explicit_square_feet_and_metre_conversion():
    assert extract('Anggaran Saiz (Jika tahu): 1,500 sqft')['area_sqft']==1500
    assert abs(extract('Size: 100 sq meter')['area_sqft']-1076.39)<0.01

def test_no_unverified_dimensions_or_address_floor_counts():
    assert np.isnan(extract('Saiz: 20x70')['area_sqft'])
    assert np.isnan(extract('Address: 10th Floor, business tower')['floors_mentioned'])
    assert extract('Size: 7500sqft (3 floors)')['floors_mentioned']==3

def test_conflicting_areas_remain_unknown_and_html_decodes():
    assert np.isnan(extract('Ground floor 1370 sqf, upstairs 1650 sqf')['area_sqft'])
    assert extract('<p>Size: 850sf</p>')['area_sqft']==850
    assert np.isnan(extract('Size: tak tahu')['area_sqft'])
