import numpy as np
import pandas as pd
import pytest
from scripts.test_return_probability_calibration import mature_training,metrics,calibrate

def test_calibration_training_excludes_immature_outcomes_and_assessment_properties():
    frame=pd.DataFrame({'outcome_end_date':pd.to_datetime(['2025-06-01','2025-06-02','2025-06-03','2025-07-01']),
        'validation_group':['a','b','held','c'],'warranty_signal_within_30d':[0,1,1,1]})
    result=mature_training(frame,'2025-07-01',pd.DataFrame({'validation_group':['held']}))
    assert result.validation_group.tolist()==['a','b']

def test_metric_counts_match_threshold_decisions():
    data=pd.DataFrame({'warranty_signal_within_30d':[0,0,1,1]})
    result=metrics(data,np.array([.1,.6,.7,.3]),.5)
    assert (result['TP'],result['FP'],result['FN'],result['TN'])==(1,1,1,1)
    assert result['precision']==result['recall']==result['accuracy']==.5

@pytest.mark.parametrize('method',['raw','sigmoid','logit','beta','isotonic'])
def test_candidate_probabilities_are_bounded_and_finite(method):
    training=pd.DataFrame({'raw_probability':[0.,.1,.3,.5,.7,1.],
        'warranty_signal_within_30d':[0,0,1,0,1,1]})
    p=calibrate(training,training,method)
    assert np.isfinite(p).all() and (p>=0).all() and (p<=1).all()
