import copy
import pandas as pd
from scripts.research_programme_end_purchase import build,partition

def inputs():
    current={'sale_id':'C1','programme_id':'SALE_rawhash:1','date':'2025-01-01','sales_rm':200,'premise':'RESIDENTIAL','pest':'Cockroach','district':'Petaling'}
    next_sale={**current,'sale_id':'C2','programme_id':'SALE_otherhash:2','date':'2025-05-01','sales_rm':999}
    b={'customers':[{'customer_key':'verified-customer','identity_status':'exact_name_and_phone','sales':[current,next_sale]}]}
    e=[{'programme_id':'SALE_C1','event_date_local':'2025-04-01','event_category':'service','warranty_claim_candidate':False,
        'paid_programme_stage':None,'session_current':3,'session_total':3}]
    p=[{'programme_id':'SALE_C1','has_cancelled_sale':False,'effective_paid_sessions':3}]
    return b,e,p

def test_sale_id_canonicalisation_and_future_purchase_label():
    b,e,p=inputs();rows,audit=build(b,e,p,'2025-07-01')
    assert len(rows)==1 and rows.iloc[0].label==1 and rows.iloc[0].programme=='SALE_C1'
    assert rows.iloc[0].prior_programmes==0 and rows.iloc[0].programme_sales_rm==200

def test_future_purchase_value_never_becomes_an_input():
    b,e,p=inputs();before,_=build(b,e,p,'2025-07-01')
    b['customers'][0]['sales'][1]['sales_rm']=100000
    after,_=build(b,e,p,'2025-07-01')
    pd.testing.assert_frame_equal(before,after)

def test_unknown_recorded_amount_is_missing_not_zero():
    b,e,p=inputs();b['customers'][0]['sales'][0]['sales_rm']=None
    rows,_=build(b,e,p,'2025-07-01')
    assert pd.isna(rows.iloc[0].programme_sales_rm)

def test_outcome_boundary_and_already_purchased_exclusion():
    b,e,p=inputs();b['customers'][0]['sales'][1]['date']='2025-06-30'
    assert build(b,e,p,'2025-07-01')[0].iloc[0].label==1
    b['customers'][0]['sales'][1]['date']='2025-07-01'
    assert build(b,e,p,'2025-07-01')[0].iloc[0].label==0
    b['customers'][0]['sales'][1]['date']='2025-04-01'
    rows,audit=build(b,e,p,'2025-07-01');assert rows.empty and audit['another_programme_already_recorded']==1

def test_warranty_is_not_a_final_paid_visit_and_immature_labels_are_unknown():
    b,e,p=inputs();e[0]['warranty_claim_candidate']=True
    assert build(b,e,p,'2025-07-01')[0].empty
    e[0]['warranty_claim_candidate']=False
    rows,audit=build(b,e,p,'2025-06-29');assert rows.empty and audit['outcome_not_mature']==1

def test_ambiguous_final_visit_or_identity_not_used():
    b,e,p=inputs();e.append(copy.deepcopy(e[0]))
    rows,audit=build(b,e,p,'2025-07-01');assert rows.empty and audit['missing_or_ambiguous_final_visit']==1
    e.pop();b['customers'][0]['identity_status']='needs_review'
    assert build(b,e,p,'2025-07-01')[0].empty

def test_customer_groups_and_label_maturity_separated():
    rows=[]
    for i in range(200):
        anchor=pd.Timestamp('2021-01-01')+pd.Timedelta(days=i*7)
        rows.append({'anchor':anchor,'outcome_end':anchor+pd.Timedelta(days=90),'customer_group':str(i%110)})
    train,valid,test,_=partition(pd.DataFrame(rows))
    assert not(set(train.customer_group)&set(valid.customer_group) or set(train.customer_group)&set(test.customer_group) or set(valid.customer_group)&set(test.customer_group))
    assert train.outcome_end.max()<valid.anchor.min() and valid.outcome_end.max()<test.anchor.min()
