import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scripts import cp2_model as entry
from scripts import freeze_callback_prospective as p
from scripts import freeze_corrected_callback as corrected
from scripts import evaluate_callback_holdout as holdout


class FixedPredictor:
    def __init__(self,probability):self.probability=probability
    def predict_proba(self,frame):
        scores=np.full(len(frame),self.probability)
        return np.column_stack([1-scores,scores])


def test_bundle_adapter_supports_both_legacy_and_fixed_ensembles():
    frame=pd.DataFrame({'x':[0.,1.]})
    legacy={'pipeline':FixedPredictor(.3),'features':['x'],'calibrator':None}
    ensemble={'members':[{'pipeline':FixedPredictor(.2),'features':['x'],'weight':.25},
        {'pipeline':FixedPredictor(.8),'features':['x'],'weight':.75}],'calibrator':None}
    assert np.allclose(p.artifact_probability(legacy,frame),.3)
    assert np.allclose(p.artifact_probability(ensemble,frame),.65)


def test_registry_rejects_unreviewed_bundle_changes(tmp_path,monkeypatch):
    monkeypatch.setattr(p.b,'ROOT',tmp_path)
    (tmp_path/'config').mkdir();bundle=tmp_path/'outputs/current';bundle.mkdir(parents=True)
    (bundle/'bundle.json').write_text('{}')
    (tmp_path/'config/cp2_model_current.json').write_text(json.dumps({
        'bundle_relative_path':'outputs/current','bundle_sha256':'incorrect'}))
    with pytest.raises(ValueError,match='bundle changed'):entry.current_bundle()


def test_prediction_path_must_not_publish_customer_rows(tmp_path,monkeypatch):
    monkeypatch.setattr(p.b,'ROOT',tmp_path)
    output=tmp_path/'public/predictions.csv'
    with pytest.raises(ValueError,match='ignored'):entry.predict(tmp_path,tmp_path/'missing.json',output)
    assert not output.exists()


def test_corrected_freeze_and_final_holdout_cannot_overwrite(tmp_path):
    with pytest.raises(ValueError,match='already exists'):corrected.freeze(tmp_path/'missing',tmp_path,tmp_path)
    output=tmp_path/'final.json';output.write_text('{}')
    with pytest.raises(ValueError,match='already exists'):holdout.evaluate(tmp_path/'missing',tmp_path,output)
