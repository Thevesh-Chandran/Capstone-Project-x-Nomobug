import copy
import numpy as np
import pandas as pd
from scripts.research_quote_estimate import dataset,package_inputs,partition,price_baseline,REQUIREMENTS,CONTEXT

def inputs():
    sale={'sale_id':'S1','programme_id':'SALE_hash','customer_key':'customer','date':'2025-01-01',
          'sales_rm':799,'pest':'Cockroach','district':'Petaling'}
    facts=[{'sales_record_id':'S1','closed_date':'2025-01-01','sale_total_rm':799,'sale_total_needs_review':False,
            'package_sessions_recorded':4,'package_type_raw':'4x RM799','premise_type':'RESIDENTIAL','include_in_sale_count':True}]
    business={'customers':[{'customer_key':'customer','identity_status':'exact_name_and_phone'}], 'records':{'sales':[sale]}}
    return business,facts

def test_price_in_package_name_does_not_leak_into_inputs():
    assert package_inputs('4x RM799')==package_inputs('4x RM9999')
    assert package_inputs('2 TBS + 3 FREE GPC RM999')['tbs_units']==2
    b,f=inputs();before,_=dataset(b,f)
    f[0]['sale_total_rm']=9999;f[0]['package_type_raw']='4x RM9999';b['records']['sales'][0]['sales_rm']=9999
    after,_=dataset(b,f)
    pd.testing.assert_frame_equal(before[REQUIREMENTS+CONTEXT],after[REQUIREMENTS+CONTEXT])
    assert before.target_rm.iloc[0]!=after.target_rm.iloc[0]

def test_future_sales_and_current_sale_never_enter_purchase_history():
    b,f=inputs();b['records']['sales'][0]['date']='2024-12-01'
    b['records']['sales'].append({**b['records']['sales'][0],'sale_id':'S2','programme_id':'SALE_2','date':'2026-01-01','sales_rm':10000})
    f.append({**f[0],'sales_record_id':'S2','closed_date':'2026-01-01','sale_total_rm':10000})
    frame,_=dataset(b,f);row=frame[frame.sale_id=='S1'].iloc[0]
    assert row.prior_programmes==0 and row.prior_average_sales_rm==0

def test_untrusted_target_values_are_not_imputed_or_replaced():
    b,f=inputs();f[0]['sale_total_rm']=None
    # Keep another valid row so the returned frame has a normal schema.
    b['records']['sales'].append({**b['records']['sales'][0],'sale_id':'S2','programme_id':'SALE_2'})
    f.append({**f[0],'sales_record_id':'S2','sale_total_rm':400})
    frame,audit=dataset(b,f)
    assert frame.sale_id.tolist()==['S2'] and audit['unknown_invalid_free_or_incomplete_date']==1

def test_baseline_does_not_read_test_prices():
    b,f=inputs();frame,_=dataset(b,f);train=frame.copy();test=frame.copy();test.target_rm=10000
    pred=price_baseline(train,test);assert pred.tolist()==[799]

def test_chronological_customer_groups_do_not_overlap():
    frame=pd.DataFrame([{'date':pd.Timestamp('2024-01-01')+pd.Timedelta(days=i),'customer_group':str(i%75)} for i in range(150)])
    train,valid,test,_=partition(frame)
    assert train.date.max()<valid.date.min() and valid.date.max()<test.date.min()
    assert not(set(train.customer_group)&set(test.customer_group) or set(train.customer_group)&set(valid.customer_group) or set(valid.customer_group)&set(test.customer_group))

def test_per_session_regressor_returns_total_without_reading_current_price():
    from sklearn.dummy import DummyRegressor
    from scripts.research_quote_estimate import PerSessionRegressor
    model=PerSessionRegressor(DummyRegressor()).fit(pd.DataFrame({'sessions':[3,6]}),np.array([300,600]))
    assert model.predict(pd.DataFrame({'sessions':[12]})).tolist()==[1200]
