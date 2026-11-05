from scripts.forward_select_return_predictors import acceptable
from scripts.forward_select_return_predictors import pipeline
import pandas as pd


def result(values):
    return {'mean_f1':sum(values)/len(values),'folds':[{'f1':x} for x in values]}


def test_single_period_gain_cannot_hide_large_other_period_loss():
    assert not acceptable(result([.4,.4]),result([.6,.35]))


def test_tiny_gain_does_not_trigger_an_addition():
    assert not acceptable(result([.4,.4]),result([.403,.403]))


def test_material_consistent_improvement_is_accepted():
    assert acceptable(result([.4,.4]),result([.41,.42]))


def test_single_normalized_pest_input_is_encoded_as_category():
    x=pd.DataFrame({'normalized_pest_category':['COCKROACH','ANT']*20})
    model=pipeline(['normalized_pest_category'])
    model.fit(x,[True,False]*20)
    assert model.predict_proba(x).shape==(40,2)
