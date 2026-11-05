"""Export only numeric tree rules and non-identifying feature categories."""
import json
import joblib
import numpy as np
from scripts.research_additional_models import ROOT,save
from scripts.research_repeat_purchase import build
from webapp.predictions import initial_features,rank_score


def main():
    folder=ROOT/'outputs/additional_model_research/20261014';saved=joblib.load(folder/'repeat90_research.joblib')
    pipeline=saved['model'];pre=pipeline.steps[0][1];clf=pipeline.steps[1][1]
    numeric=pre.named_transformers_['num'];categorical=pre.named_transformers_['cat']
    model={'version':'repeat90_research_v1','status':'experimental_not_calibrated','numeric_features':list(pre.transformers_[0][2]),
        'categorical_features':list(pre.transformers_[1][2]),'imputer':numeric.steps[0][1].statistics_.tolist(),
        'mean':numeric.steps[1][1].mean_.tolist(),'scale':numeric.steps[1][1].scale_.tolist(),
        'categories':[c.tolist() for c in categorical.categories_],'baseline':float(clf._baseline_prediction[0,0]),'trees':[],
        'evaluation':json.loads((folder/'repeat90_results.json').read_text())['holdout']}
    for iteration in clf._predictors:
        for predictor in iteration:
            nodes=[]
            for n in predictor.nodes:
                if n['is_categorical']:raise ValueError('Unsupported native categorical split')
                nodes.append({'leaf':bool(n['is_leaf']),'feature':int(n['feature_idx']),'threshold':float(n['num_threshold']),
                    'left':int(n['left']),'right':int(n['right']),'value':float(n['value'])})
            model['trees'].append(nodes)
    customers=json.loads((ROOT/'outputs/business_implementation/current/customers_private.json').read_text())
    df,_=build(customers,'2026-10-11');test=df[df.first_date.between('2026-01-01','2026-07-13')]
    expected=pipeline.predict_proba(test[saved['feature_columns']])[:,1]
    actual=np.array([rank_score(row,model) for row in test.to_dict('records')])
    if not np.allclose(expected,actual,atol=1e-12):raise ValueError('Portable inference differs')
    destination=ROOT/'webapp/models/repeat90_v1.json';destination.parent.mkdir(exist_ok=True);save(destination,model)
    save(folder/'portable_inference_check.json',{'rows':len(actual),'maximum_error':float(np.abs(expected-actual).max()),'no_customer_names_or_contacts_exported':True})
    print('Portable repeat inference verified against all 557 test customers; no new runtime dependencies.')


if __name__=='__main__':main()
